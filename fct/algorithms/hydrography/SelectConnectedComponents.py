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

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsVectorLayer
)

from ..metadata import AlgorithmMetadata

class SelectConnectedComponents(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Select links connected to selected ones
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectConnectedComponents')

    INPUT = 'INPUT'
    # OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    DIRECTION = 'DIRECTION'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream network (polylines)'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        self.addParameter(QgsProcessingParameterEnum(
            self.DIRECTION,
            self.tr('Direction'),
            options=[self.tr(option) for option in ['Upstream', 'Downstream', 'Up/Downstream', 'Undirected']],
            defaultValue=0))

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Strahler Order'),
        #     QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        direction = self.parameterAsInt(parameters, self.DIRECTION, context)

        selection = set()

        def selectConnectedLinksUndirected():

            feedback.setProgressText(self.tr("Build layer index ..."))

            # Index : Node -> List of edges connnected to Node
            node_index = defaultdict(list)

            total = 100.0 / layer.featureCount() if layer.featureCount() else 0

            for current, feature in enumerate(layer.getFeatures()):

                if feedback.isCanceled():
                    break

                from_node = feature.attribute(from_node_field)
                to_node = feature.attribute(to_node_field)

                node_index[from_node].append((feature.id(), to_node))
                node_index[to_node].append((feature.id(), from_node))

                feedback.setProgress(int(current * total))

            feedback.setProgressText(self.tr("Select connected links ..."))

            stack = list()
            seen_nodes = set()
            current = 0

            for feature in layer.selectedFeatures():

                if feedback.isCanceled():
                    break

                from_node = feature.attribute(from_node_field)
                to_node = feature.attribute(to_node_field)

                selection.add(feature.id())
                stack.append(from_node)
                stack.append(to_node)

                current += 1
                feedback.setProgress(int(current * total))

            while stack:

                if feedback.isCanceled():
                    break

                node = stack.pop()

                if node in seen_nodes:
                    continue

                seen_nodes.add(node)

                for fid, next_node in node_index[node]:

                    if fid not in selection:

                        selection.add(fid)
                        stack.append(next_node)

                        current += 1
                        feedback.setProgress(int(current * total))

        def selectConnectedLinksDirected(from_node_field, to_node_field):

            feedback.setProgressText(self.tr("Build layer index ..."))

            graph = defaultdict(list)
            total = 100.0 / layer.featureCount() if layer.featureCount() else 0

            for current, feature in enumerate(layer.getFeatures()):

                if feedback.isCanceled():
                    break

                from_node = feature.attribute(from_node_field)
                to_node = feature.attribute(to_node_field)
                graph[to_node].append((from_node, feature.id()))

                feedback.setProgress(int(current * total))

            feedback.setProgressText(self.tr("Select connected links ..."))

            process_stack = [(segment.attribute(from_node_field), segment.id()) for segment in layer.selectedFeatures()]

            while process_stack:

                if feedback.isCanceled():
                    break

                node, segment_id = process_stack.pop()
                selection.add(segment_id)

                for next_node, next_segment_id in graph[node]:
                    # Prevent infinite loop
                    if next_segment_id not in selection:
                        process_stack.append((next_node, next_segment_id))

        if direction == 0:
            selectConnectedLinksDirected(from_node_field, to_node_field)
        elif direction == 1:
            selectConnectedLinksDirected(to_node_field, from_node_field)
        elif direction == 2:
            selectConnectedLinksDirected(from_node_field, to_node_field)
            selectConnectedLinksDirected(to_node_field, from_node_field)
        elif direction == 3:
            selectConnectedLinksUndirected()

        layer.selectByIds(list(selection), QgsVectorLayer.SetSelection)

        return {}
