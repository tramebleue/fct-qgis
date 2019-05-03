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

from heapq import heappush, heappop
from functools import (
    partial,
    reduce,
    total_ordering
)
from collections import defaultdict

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
            defaultValue='MEAS'))

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
        adjacency = list()

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
            adjacency.append((a, b, edge.id(), measure(edge)))

            feedback.setProgress(int(current * total))

        anodes = set([a for a, b, e, d in adjacency])
        bnodes = set([b for a, b, e, d in adjacency])
        # No edge points to a source,
        # then sources are not in bnodes
        sources = anodes - bnodes

        # Index : Node A -> Edges starting from A
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 2 - Sort sources by descending distance

        queue = list()
        for source in sources:
            for a, b, edge_id, distance in aindex[source]:
                heappush(queue, SourceEntry(edge_id, distance))

        # Step 3 - Output edges starting from maximum distance source to outlet ;
        #          when outlet is reached,
        #          continue from next maximum distance source
        #          until no edge remains

        feedback.setProgressText(self.tr("Sort subgraphs by descending source distance"))

        seen_edges = dict()
        current = 0
        total = 100.0 / len(sources) if sources else 0
        feedback.setProgress(0)

        fields = layer.fields().toList() + [
            QgsField('STEMID', QVariant.Int, len=5),
            QgsField('HACK', QVariant.Int, len=5),
            QgsField('STEMLENGTH', QVariant.Double, len=10, prec=2)
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            asQgsFields(*fields), layer.wkbType(), layer.sourceCrs())

        srclayer = context.getMapLayer(layer.sourceName())

        while queue:

            if feedback.isCanceled():
                break

            entry = heappop(queue)
            edge = srclayer.getFeature(entry.key)
            process_stack = [edge]
            selection = set()
            rank = 1
            length = 0

            while process_stack:

                edge = process_stack.pop()
                selection.add(edge.id())
                length += edge.geometry().length()
                to_node = edge.attribute(to_node_field)

                if to_node in aindex:

                    edges = [e for a, b, e, d in aindex[to_node]]
                    query = QgsFeatureRequest().setFilterFids(edges)

                    for next_edge in layer.getFeatures(query):

                        next_id = next_edge.id()
                        if next_id in seen_edges:
                            rank = seen_edges[next_id] + 1
                        elif next_id not in selection:
                            process_stack.append(next_edge)

            query = QgsFeatureRequest().setFilterFids(list(selection))
            for feature in layer.getFeatures(query):

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [
                    current,
                    rank,
                    length
                ])
                sink.addFeature(outfeature)
                seen_edges[feature.id()] = rank


            current = current + 1
            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
