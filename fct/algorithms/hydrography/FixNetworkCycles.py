# -*- coding: utf-8 -*-

"""
Fix Network Cycles

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
import itertools

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

class NodeData(object):

    def __init__(self, index):
        self.index = index
        self.lowlink = index

class FixNetworkCycles(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Find cycles (ie. loops) in the directed hydrographic network,
    and try to apply an automatic fix to remove those cycles.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FixNetworkCycles')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
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

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Fixed Cycles'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, fb): #pylint: disable=unused-argument,missing-docstring

        feedback = QgsProcessingMultiStepFeedback(3, fb)

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        feedback.setCurrentStep(0)
        feedback.setProgressText(self.tr("Build graph index ..."))

        # Directed graph from node A to (node B, edge id)
        graph = defaultdict(list)
        indegree = Counter()
        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            graph[from_node].append((to_node, feature.id()))
            # graph.get(to_node)
            if to_node not in graph:
                graph[to_node] = list()
            indegree[to_node] += 1

            feedback.setProgress(int(current * total))

        feedback.setCurrentStep(1)
        feedback.setProgressText(self.tr("Find cycles ..."))

        stack = list()
        index = itertools.count()
        seen_nodes = dict()

        def fix_cycle(origin, cycle):
            """
            Fix undirected graph `cycle` from `origin`
            """

            stack = [origin]
            regraph = defaultdict(list)
            seen_edges = set()

            while stack:

                if feedback.isCanceled():
                    return

                node = stack.pop()
                outernodes = [(a, fid) for a, fid in graph[node] if a not in cycle]
                outdegree = len(outernodes)

                for next_node, next_edge in cycle[node]:

                    if next_edge not in seen_edges:

                        regraph[node].append((next_node, next_edge))
                        seen_edges.add(next_edge)

                        if outdegree == 0:
                            stack.append(next_node)

                regraph[node].extend(outernodes)

            graph.update(regraph)

        def connect(node):
            """
            Tarjan Strongly Connected Component Algorithm
            https://en.wikipedia.org/wiki/Tarjan%27s_strongly_connected_components_algorithm
            """

            current_index = next(index)
            data = NodeData(current_index)
            seen_nodes[node] = data
            stack.append(node)

            for next_node, next_feature_id in graph[node]:
                if next_node not in seen_nodes:
                    connect(next_node)
                    if feedback.isCanceled():
                        return
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].lowlink)
                elif next_node in stack:
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].index)

            if data.index == data.lowlink:

                cycle = defaultdict(list)
                first_back_node = stack.pop()

                if first_back_node != node:
                    for next_node, feature_id in graph[first_back_node]:
                        if next_node == node:
                            cycle[next_node].append((first_back_node, feature_id))
                            cycle[first_back_node].append((next_node, feature_id))
                    # else:
                    #     ProcessingLog.addToLog(
                    #         ProcessingLog.LOG_INFO,
                    #         "Unmatched feature : %d -> %d" % (first_back_node, node))

                back_node = first_back_node
                while node != back_node:
                    next_back_node = stack.pop()
                    for next_node, feature_id in graph[next_back_node]:
                        if next_node == back_node:
                            cycle[next_node].append((next_back_node, feature_id))
                            cycle[next_back_node].append((next_node, feature_id))
                    back_node = next_back_node

                fix_cycle(node, cycle)

        # Walk from sources to outlets, rather than randomly ;
        # it should help to find a better origin node
        # when we need to fix cycles.

        # for node in graph:

        #     if feedback.isCanceled():
        #         break

        #     if node not in seen_nodes:
        #         connect(node)

        stack = [node for node in graph if indegree[node] == 0]

        while stack:

            if feedback.isCanceled():
                break

            node = stack.pop(0)

            if node not in seen_nodes:
                connect(node)

            for next_node, feature_id in graph[node]:

                indegree[next_node] -= 1

                if indegree[next_node] == 0:
                    stack.append(next_node)

        feedback.setCurrentStep(2)
        feedback.setProgressText(self.tr('Output fixed features'))

        edges = {edge: (a, b) for a in graph for b, edge in graph[a]}

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('FIXED', QVariant.Int, len=1), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        fixed_count = 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)
            edge = feature.id()

            if edge in edges:

                a, b = edges[edge]
                if a == from_node and b == to_node:

                    outfeature = QgsFeature()
                    outfeature.setGeometry(feature.geometry())
                    outfeature.setAttributes(feature.attributes() + [
                        False
                    ])
                    sink.addFeature(outfeature)

                else:

                    feature[from_node_field] = a
                    feature[to_node_field] = b
                    geometry = QgsGeometry(QgsLineString(reversed([v for v in feature.geometry().vertices()])))
                    outfeature = QgsFeature(fields)
                    outfeature.setGeometry(geometry)
                    outfeature.setAttributes(feature.attributes() + [
                        True
                    ])
                    outfeature.setGeometry(geometry)
                    sink.addFeature(outfeature)

                    fixed_count += 1

            else:

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes + [
                    False
                ])
                sink.addFeature(outfeature)

            feedback.setProgress(int(current * total))

        feedback.pushInfo('Fixed %d features.' % fixed_count)

        return {self.OUTPUT: dest_id}
