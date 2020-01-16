# -*- coding: utf-8 -*-

"""
SelectConnectedComponents - Select Connected Components

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict, Counter

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsVectorLayer,
    NULL
)


from ..metadata import AlgorithmMetadata

class SelectHeadwaterBasins(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Select headwater basins,
    ie. basins having no upstream basin.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectHeadwaterBasins')

    INPUT = 'INPUT'
    # OUTPUT = 'OUTPUT'
    ID_FIELD = 'ID_FIELD'
    DOWNSTREAM_FIELD = 'DOWNSTREAM_FIELD'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Basins'),
            [QgsProcessing.TypeVectorAnyGeometry]))

        self.addParameter(QgsProcessingParameterField(
            self.ID_FIELD,
            self.tr('ID Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterField(
            self.DOWNSTREAM_FIELD,
            self.tr('Downstream Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='AVAL'))

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Strahler Order'),
        #     QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        id_field = self.parameterAsString(parameters, self.ID_FIELD, context)
        downstream_field = self.parameterAsString(parameters, self.DOWNSTREAM_FIELD, context)

        findex = dict()
        graph = dict()
        indegree = Counter()

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        feedback.setProgressText(self.tr("Build network graph ..."))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            gid = feature.attribute(id_field)
            downstream = feature.attribute(downstream_field)

            findex[gid] = feature.id()

            if downstream != NULL:

                graph[gid] = downstream
                indegree[downstream] += 1

            feedback.setProgress(int(current * total))

        selection = [findex[component] for component in graph if indegree[component] == 0]

        layer.selectByIds(selection, QgsVectorLayer.SetSelection)

        return {}
