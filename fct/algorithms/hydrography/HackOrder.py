# -*- coding: utf-8 -*-

"""
LengthOrder

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from heapq import heappush, heappop, heapify
from functools import (
    partial,
    reduce,
    total_ordering
)

from collections import defaultdict, Counter

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module,import-error
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module,import-error
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

def index_by(i, d, x):
    d[x[i]].append(x)
    return d

@total_ordering
class SourceEntry(object):

    def __init__(self, key, distance):
        self.key = key
        # Use negative distance to sort sources
        # by descending distance to outlet (max heap)
        self.distance = -distance

    def __hash__(self):
        return self.key.__hash__()

    def __lt__(self, other):
        return self.distance < other.distance

    def __eq__(self, other):
        return self.distance == other.distance


class HackOrder(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Length-wise stream order, aka. Hack order, of each link in a stream network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'HackOrder')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    MEASURE_FIELD = 'MEASURE_FIELD'
    IS_DOWNSTREAM_MEAS = 'IS_DOWNSTREAM_MEAS'
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

        self.addParameter(QgsProcessingParameterField(
            self.MEASURE_FIELD,
            self.tr('Measure Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='MEASURE'))

        self.addParameter(QgsProcessingParameterBoolean(
            self.IS_DOWNSTREAM_MEAS,
            self.tr('Add Feature Length To Downstream Measure'),
            defaultValue=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Hack Order'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        distance_field = self.parameterAsString(parameters, self.MEASURE_FIELD, context)
        is_downstream = self.parameterAsBool(parameters, self.IS_DOWNSTREAM_MEAS, context)

        # Step 1 - Find sources and build djacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        
        graph = defaultdict(list) # A -> list of (B, fid)
        distances = defaultdict(lambda: 0) # distance from A to outlet
        indegree = Counter() # Number of edges reaching node B

        if is_downstream:

            def measure(edge):
                """
                Return upstream measure (ie. add geometry length)
                """
                return edge.attribute(distance_field) + edge.geometry().length()

        else:

            def measure(edge):
                """
                Return measure field
                """
                return edge.attribute(distance_field)

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            distance = measure(edge)

            graph[a].append((b, edge.id()))
            indegree[b] += 1
            distances[a] = max(distance, distances[a])

            feedback.setProgress(int(current * total))

        # Step 2 - Sort sources by descending distance

        # sources = [a for a in graph if indegree[a] == 0]
        # queue = heapify([SourceEntry(source, distances[source]) for source in sources])

        queue = [SourceEntry(a, distances[a]) for a in graph if indegree[a] == 0]
        heapify(queue)

        # Step 3 - Output edges starting from maximum distance source to outlet ;
        #          when outlet is reached,
        #          continue from next maximum distance source
        #          until no edge remains

        feedback.setProgressText(self.tr("Sort subgraphs by descending source distance"))

        fields = layer.fields().toList() + [
            QgsField('AXIS', QVariant.Int, len=5),
            QgsField('LAXIS', QVariant.Double, len=10, prec=2),
            QgsField('HACK', QVariant.Int, len=5)
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            asQgsFields(*fields), layer.wkbType(), layer.sourceCrs())

        seen_edges = defaultdict(lambda: 0)
        seen_nodes = set()
        current = 1
        total = 100.0 / len(queue) if queue else 0
        feedback.setProgress(0)

        def node_rank(node):
            """
            Return the minimum rank of edges starting from 'node'
            """

            rank = 0

            for b, edge in graph[node]:
                if rank == 0:
                    rank = seen_edges[edge]
                else:
                    rank = min(rank, seen_edges[edge])

            return rank

        # Iterate sources by descending distance

        while queue:

            if feedback.isCanceled():
                break

            entry = heappop(queue)
            a = entry.key
            rank = 1
            edges = set()
            axis_length = distances[a]
            downstream_measure = 0

            # Walk down the network from A until we reach
            # some part we have already explored.

            stack = [a]

            while stack:

                a = stack.pop()

                for b, edge in graph[a]:

                    edges.add(edge)

                    if b in seen_nodes:

                        rank = max(rank, node_rank(b) + 1)

                        if downstream_measure == 0:
                            downstream_measure = distances[b]
                        else:
                            downstream_measure = min(downstream_measure, distances[b])

                    else:

                        seen_nodes.add(b)
                        stack.append(b)

            query = QgsFeatureRequest().setFilterFids(list(edges))

            for feature in layer.getFeatures(query):

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [
                    current,
                    (axis_length - downstream_measure),
                    rank
                ])
                sink.addFeature(outfeature)
                seen_edges[feature.id()] = rank

            current = current + 1
            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
