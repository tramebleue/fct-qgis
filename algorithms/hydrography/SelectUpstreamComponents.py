# -*- coding: utf-8 -*-

"""
SelectUpstreamComponents - Select Upstream Components

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsExpression,
    QgsGeometry,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsVectorLayer
)

from ..metadata import AlgorithmMetadata

class SelectUpstreamComponents(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Select upstream links connected to selected ones
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectUpstreamComponents')

    INPUT = 'INPUT'
    # OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream network (polylines)'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Strahler Order'),
        #     QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        feedback.setProgressText(self.tr("Build layer index ..."))

        to_node_index = defaultdict(list)
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            to_node = feature.attribute(to_node_field)
            to_node_index[to_node].append(feature.id())

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Select connected links ..."))

        process_stack = [segment for segment in layer.selectedFeatures()]
        selection = set()

        while process_stack:

            segment = process_stack.pop()
            selection.add(segment.id())
            from_node = segment.attribute(from_node_field)

            if from_node in to_node_index:
                query = QgsFeatureRequest().setFilterFids(to_node_index[from_node])
                for next_segment in layer.getFeatures(query):
                    # Prevent infinite loop
                    if next_segment.id() not in selection:
                        process_stack.append(next_segment)

        layer.selectByIds(list(selection), QgsVectorLayer.SetSelection)

        return {}
