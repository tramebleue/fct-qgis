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

from collections import defaultdict

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

class SelectConnectedBasins(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Select upstream or downstream basins from selected ones.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectConnectedBasins')

    INPUT = 'INPUT'
    # OUTPUT = 'OUTPUT'
    ID_FIELD = 'ID_FIELD'
    DOWNSTREAM_FIELD = 'DOWNSTREAM_FIELD'
    DIRECTION = 'DIRECTION'

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

        self.addParameter(QgsProcessingParameterEnum(
            self.DIRECTION,
            self.tr('Direction'),
            options=[self.tr(option) for option in ['Upstream', 'Downstream', 'Both']],
            defaultValue=0))

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Strahler Order'),
        #     QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        id_field = self.parameterAsString(parameters, self.ID_FIELD, context)
        downstream_field = self.parameterAsString(parameters, self.DOWNSTREAM_FIELD, context)
        direction = self.parameterAsInt(parameters, self.DIRECTION, context)

        findex = dict()
        graph = dict()
        reverse_graph = defaultdict(list)
        selection = set()

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
                reverse_graph[downstream].append(gid)

            feedback.setProgress(int(current * total))

        def select_upstream_components():

            feedback.setProgressText(self.tr("Select upward ..."))
            seen = set()

            for feature in layer.selectedFeatures():

                if feedback.isCanceled():
                    break

                stack = [feature.attribute(id_field)]

                while stack:

                    component = stack.pop()
                    if component in seen:
                        continue

                    fid = findex[component]
                    selection.add(fid)
                    seen.add(component)

                    for upward in reverse_graph[component]:
                        stack.append(upward)

        def select_downstream_components():

            feedback.setProgressText(self.tr("Select downward ..."))
            seen = set()

            for feature in layer.selectedFeatures():

                if feedback.isCanceled():
                    break

                component = feature.attribute(id_field)

                while True:

                    if component in seen:
                        break

                    if component not in findex:
                        break

                    fid = findex[component]
                    selection.add(fid)
                    seen.add(component)

                    if component in graph:
                        component = graph[component]
                    else:
                        break

        if direction == 0:
            select_upstream_components()
        elif direction == 1:
            select_downstream_components()
        elif direction == 2:
            select_upstream_components()
            select_downstream_components()

        layer.selectByIds(list(selection), QgsVectorLayer.SetSelection)

        return {}
