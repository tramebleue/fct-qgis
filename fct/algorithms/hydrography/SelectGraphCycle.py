# -*- coding: utf-8 -*-

"""
Select Graph Cycles

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
    QgsFeatureRequest,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsVectorLayer
)

from ..metadata import AlgorithmMetadata

class NodeData(object):

    def __init__(self, index):
        self.index = index
        self.lowlink = index


class SelectGraphCycle(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Select cycles (ie. loops) in hydrographic network.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectGraphCycle')

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
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        feedback.setProgressText(self.tr("Build graph index ..."))

        node_index = dict()
        feature_index = defaultdict(list)
        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            if from_node in node_index:
                node_index[from_node].append(to_node)
            else:
                node_index[from_node] = [to_node]

            if to_node not in node_index:
                node_index[to_node] = list()
                
            feature_index[(from_node, to_node)].append(feature.id())

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Find cycles ..."))

        stack = list()
        self.index = 0
        seen_nodes = dict()
        selection = set()

        def connect(node):
            """
            Tarjan Strongly Connected Component Algorithm
            https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm
            """

            data = NodeData(self.index)
            seen_nodes[node] = data
            self.index = self.index + 1
            stack.append(node)

            for next_node in node_index[node]:
                if next_node not in seen_nodes:
                    connect(next_node)
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].lowlink)
                elif next_node in stack:
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].index)

            if data.index == data.lowlink:

                first_back_node = stack.pop()

                if first_back_node != node:
                    if (first_back_node, node) in feature_index:
                        for feature_id in feature_index[(first_back_node, node)]:
                            selection.add(feature_id)
                    # else:
                    #     ProcessingLog.addToLog(
                    #         ProcessingLog.LOG_INFO,
                    #         "Unmatched feature : %d -> %d" % (first_back_node, node))

                back_node = first_back_node
                while node != back_node:
                    next_back_node = stack.pop()
                    for feature_id in feature_index[(next_back_node, back_node)]:
                        selection.add(feature_id)
                    back_node = next_back_node

            # progress.setPercentage(int(current * total))

        for node in node_index:

            if feedback.isCanceled():
                break

            if node not in seen_nodes:
                connect(node)

        layer.selectByIds(list(selection), QgsVectorLayer.SetSelection)

        return {}
