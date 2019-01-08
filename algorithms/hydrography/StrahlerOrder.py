# -*- coding: utf-8 -*-

"""
StrahlerOrder - Horton-Strahler stream order of each link in a stream network

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from functools import partial, reduce
from collections import defaultdict

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata

def index_by(i, accumulator, x):
    """
    Parameters
    ----------

    i: index of tuple member to index by
    d: dict-like accumulator
    x: data tuple
    """

    accumulator[x[i]].append(x)
    return accumulator

def count_by(i, accumulator, x):
    """
    Parameters
    ----------

    i: index of tuple member to count by
    d: dict-like accumulator
    x: data tuple
    """

    accumulator[x[i]] = accumulator[x[i]] + 1
    return accumulator

def asQgsFields(*fields):
    """ Turn list-of-fields into QgsFields object
    """

    out = QgsFields()
    for field in fields:
        out.append(field)
    return out

class StrahlerOrder(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Horton-Strahler stream order of each link in a stream network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StrahlerOrder')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    OUTPUT = 'OUTPUT'

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

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Strahler Order'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        # Step 1 - Build adjacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        adjacency = list()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append((a, b, edge.id()))

            feedback.setProgress(int(current * total))

        # Step 2 - Find sources and compute confluences in-degree

        anodes = set([a for a, b, e in adjacency])
        bnodes = set([b for a, b, e in adjacency])
        # No edge points to a source,
        # then sources are not in bnodes
        sources = anodes - bnodes

        # Confluences in-degree
        bcount = reduce(partial(count_by, 1), adjacency, defaultdict(lambda: 0))
        confluences = {node: indegree for node, indegree in bcount.items() if indegree > 1}

        # Index : Node A -> Edges starting from A
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 3 - Prune sources/leaves iteratively

        feedback.setProgressText(self.tr("Enumerate links by Strahler order ..."))

        current = 0
        feedback.setProgress(0)

        fields = layer.fields().toList() + [
            QgsField('STRAHLER', QVariant.Int, len=5),
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            asQgsFields(*fields), layer.wkbType(), layer.sourceCrs())

        queue = list(sources)
        order = 1
        srclayer = context.getMapLayer(layer.sourceName())

        while True:

            if feedback.isCanceled():
                break

            while queue:

                if feedback.isCanceled():
                    break

                a = queue.pop()

                for a, b, edgeid in aindex[a]:

                    edge = srclayer.getFeature(edgeid)
                    feature = QgsFeature()
                    feature.setGeometry(edge.geometry())
                    feature.setAttributes(edge.attributes() + [
                        order
                    ])
                    sink.addFeature(feature)

                    current = current + 1
                    feedback.setProgress(int(current * total))

                    if b in confluences:
                        confluences[b] = confluences[b] - 1
                    else:
                        queue.append(b)

            queue = [node for node, indegree in confluences.items() if indegree == 0]
            confluences = {node: indegree for node, indegree in confluences.items() if indegree > 1}
            order = order + 1

            # if not confluences and not queue:
            if not queue:
                break

        return {self.OUTPUT: dest_id}
