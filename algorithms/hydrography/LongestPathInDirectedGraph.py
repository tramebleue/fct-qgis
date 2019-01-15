# -*- coding: utf-8 -*-

"""
LongestPathInDirectedGraph - Find the longest path in a directed graph

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import Counter, namedtuple

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from .graph import create_link_index
from ..metadata import AlgorithmMetadata

Link = namedtuple('Link', ('a', 'b', 'edge_id', 'length'))

class LongestPathInDirectedGraph(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Find the longest path in a directed graph
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LongestPathInDirectedGraph')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    MULTIFLOW = 'MULTIFLOW'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Directed Graph'),
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

        self.addParameter(QgsProcessingParameterBoolean(
            self.MULTIFLOW,
            self.tr('Extract multi-path'),
            defaultValue=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Longest Path'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        mutliflow = self.parameterAsBool(parameters, self.MULTIFLOW, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs())

        # Step 1

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        adjacency = list()
        outdegree = Counter()

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append(Link(a, b, edge.id(), edge.geometry().length()))

            outdegree[a] += 1

            feedback.setProgress(int(current * total))

        # sources = set([link.a for link in adjacency]) - set([link.b for link in adjacency])
        outlets = set(link.b for link in adjacency if outdegree[link.b] == 0)

        def key(link):
            """ Index by node b """
            return link.b

        upward_index = create_link_index(adjacency, key)

        # Step 2

        feedback.setProgressText(self.tr("Search for longest path ..."))

        distances = {node: 0.0 for node in outlets}
        max_distance = 0.0
        max_node = None
        stack = list(outlets)
        backtracks = dict()

        current = 0
        seen_nodes = set()
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        while stack:

            if feedback.isCanceled():
                break

            node = stack.pop()
            if node in seen_nodes:
                continue

            seen_nodes.add(node)

            distance = distances[node]
            if distance > max_distance:
                max_distance = distance
                max_node = node

            # traverse graph until next diffluence

            for link in upward_index[node]:

                dist_a = distances.get(link.a, 0.0)

                if dist_a < distance + link.length:

                    dist_a = distances[link.a] = distance + link.length
                    backtracks[link.a] = link

                # check if link.a is a diffluence
                if outdegree[link.a] > 1:
                    outdegree[link.a] -= 1
                    continue

                # otherwise process upward
                stack.append(link.a)

            current = current + 1
            feedback.setProgress(int(current * total))

        # Step 3

        feedback.setProgressText(self.tr("Output longest path ..."))
        srclayer = context.getMapLayer(layer.sourceName())

        node = max_node
        count = 0

        if mutliflow:

            downward_index = create_link_index(adjacency, lambda link: link.a)
            stack = [max_node]
            seen_nodes = set()

            while stack:

                node = stack.pop()
                if node in seen_nodes:
                    continue

                seen_nodes.add(node)

                for link in downward_index[node]:

                    feature = srclayer.getFeature(link.edge_id)
                    sink.addFeature(feature)
                    count += 1

                    if link.b in downward_index:
                        stack.append(link.b)

        else:

            while node in backtracks:

                link = backtracks[node]
                feature = srclayer.getFeature(link.edge_id)
                sink.addFeature(feature)
                count += 1

                node = link.b

        feedback.pushInfo(
            self.tr('Longest path is %d segments long, for a total length of %f') \
            % (count, max_distance))

        return {
            self.OUTPUT: dest_id
        }
