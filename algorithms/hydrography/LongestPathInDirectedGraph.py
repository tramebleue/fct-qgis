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

from heapq import heappush, heappop
from functools import total_ordering
from functools import partial, reduce
from collections import defaultdict, namedtuple

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from .graph import create_link_index
from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

Link = namedtuple('Link', ('a', 'b', 'edge_id', 'length'))

class PathInfo(object):

    def __init__(self, start_node):

        self.start_node = start_node
        self.end_node = None
        self.length = 0
        self.edges = list()
        self.diverging = False

    def add(self, node, edge, new_length):

        self.end_node = node
        self.edges.append(edge)
        self.length = new_length
        return self

class NodeInfo(object):

    def __init__(self, node, length=0.0, path=None):

        self.node = node
        self.length = length
        self.out_degree = 0
        if path is None:
            path = PathInfo(self)
        self.path = path
        self.index = -1

    def add(self, node, edge, new_length):
        
        path = self.path
        self.index = len(path.edges) - 1

        successor = NodeInfo(node, new_length, path)
        self.out_degree = self.out_degree + 1
        path.add(successor, edge, new_length)

        return successor

    def divergesTo(self, b):

        return self.path.start_node.node == b.path.start_node.node


class LongestPathInDirectedGraph(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Find the longest path in a directed graph
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LongestPathInDirectedGraph')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
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
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Longest Path'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

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

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append(Link(a, b, edge.id(), edge.geometry().length()))
            feedback.setProgress(int(current * total))

        sources = set([link.a for link in adjacency]) - set([link.b for link in adjacency])

        def key(link):
            """ Index by node a """
            return link.a

        aindex = create_link_index(adjacency, key)

        # Step 2

        feedback.setProgressText(self.tr("Search for longest path ..."))

        seen_nodes = dict()
        max_length = 0
        max_path = None
        stack = list(sources)

        for source in sources:
            seen_nodes[source] = NodeInfo(source)

        while stack:

            node = stack.pop()

            if node not in aindex:
                continue

            for link in aindex[node]:

                current_length = seen_nodes[link.a].length + link.length

                if link.b in seen_nodes:

                    if seen_nodes[link.a].divergesTo(seen_nodes[link.b]):

                        feedback.pushInfo("Closing diverticule")
                        junction = seen_nodes[link.a].add(link.b, link.edge_id, current_length)
                        if seen_nodes[link.b].length < current_length:
                            seen_nodes[link.b] = junction
                            continue

                    if seen_nodes[link.b].length >= current_length:
                        continue

                seen_nodes[link.b] = seen_nodes[link.a].add(link.b, link.edge_id, current_length)
                stack.append(link.b)

                if current_length > max_length:
                    max_length = current_length
                    max_path = seen_nodes[link.b].path

        # while stack:

        #     node = stack.pop()

        #     if node not in aindex:
        #         continue

        #     for link in aindex[node]:

        #         current_length = seen_nodes[link.a].length + link.length

        #         if link.b in seen_nodes and seen_nodes[link.b].length >= current_length:
        #             continue

        #         seen_nodes[link.b] = seen_nodes[link.a].add(link.b, link.edge_id, current_length)
        #         stack.append(link.b)

        #         if current_length > max_length:
        #             max_length = current_length
        #             max_path = seen_nodes[link.b].paths[-1]

        # Step 3

        feedback.setProgressText(self.tr("Output longest path ..."))
        srclayer = context.getMapLayer(layer.sourceName())

        assert(max_path is not None)

        feedback.pushInfo(
            "Longest path is %.2f long with %d edges" % (max_length, len(max_path.edges)))

        total = 100.0 / len(max_path.edges) if max_path.edges else 0

        for current, edge_id in enumerate(max_path.edges):

            edge = srclayer.getFeature(edge_id)
            sink.addFeature(edge)
            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
