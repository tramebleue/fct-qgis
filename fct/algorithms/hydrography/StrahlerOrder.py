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
from collections import defaultdict, Counter

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

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

class StrahlerOrder(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Horton-Strahler stream order of each link in a stream network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StrahlerOrder')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    AXIS_FIELD = 'AXIS_FIELD'
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
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        self.addParameter(QgsProcessingParameterField(
            self.AXIS_FIELD,
            self.tr('Axis Id'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='AXIS',
            optional=False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Strahler Order'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, fb): #pylint: disable=unused-argument,missing-docstring

        feedback = QgsProcessingMultiStepFeedback(3, fb)

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        axis_field = self.parameterAsString(parameters, self.AXIS_FIELD, context)

        # Step 1 - Build adjacency index

        feedback.setCurrentStep(0)
        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        adjacency = list()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            axis = edge.attribute(axis_field) if axis_field else None
            adjacency.append((a, b, edge.id(), axis))

            feedback.setProgress(int(current * total))

        # Step 2 - Find sources and compute confluences in-degree

        anodes = set([a for a, b, e, axis in adjacency])
        bnodes = set([b for a, b, e, axis in adjacency])
        # No edge points to a source,
        # then sources are not in bnodes
        sources = anodes - bnodes

        # Confluences in-degree
        if axis_field:

            bcount = Counter()
            baxis = set()
            
            for a, b, e, axis in adjacency:
                if not (b, axis) in baxis:
                    bcount[b] += 1
                    baxis.add((b, axis))

            del baxis

        else:

            bcount = reduce(partial(count_by, 1), adjacency, defaultdict(lambda: 0))
        
        confluences = {node: indegree for node, indegree in bcount.items() if indegree > 1}

        # Index : Node A -> Edges starting from A
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 3 - Prune sources/leaves iteratively

        feedback.setCurrentStep(1)
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

        # seen_nodes = set()
        edges = dict()
        baxis = set()

        while True:

            if feedback.isCanceled():
                break

            while queue:

                if feedback.isCanceled():
                    break

                a = queue.pop()

                # if a in seen_nodes:
                #     continue

                # seen_nodes.add(a)

                for a, b, edgeid, axis in aindex[a]:

                    # edge = srclayer.getFeature(edgeid)
                    # feature = QgsFeature()
                    # feature.setGeometry(edge.geometry())
                    # feature.setAttributes(edge.attributes() + [
                    #     order
                    # ])
                    # sink.addFeature(feature)

                    # edges[edgeid] = order
                    # current = current + 1
                    # feedback.setProgress(int(current * total))

                    if edgeid in edges:

                        if edges[edgeid] >= order:
                            continue
                        else:
                            edges[edgeid] = order

                    else:

                        edges[edgeid] = order
                        current = current + 1
                        feedback.setProgress(int(current * total))

                    if b in confluences:
                        if not (b, axis) in baxis:
                            confluences[b] = confluences[b] - 1
                            baxis.add((b, axis))
                    else:
                        queue.append(b)

            queue = [node for node, indegree in confluences.items() if indegree == 0]
            confluences = {node: indegree for node, indegree in confluences.items() if indegree > 1}
            order = order + 1

            # if not confluences and not queue:
            if not queue:
                break

        feedback.setCurrentStep(2)
        feedback.setProgressText(self.tr('Output features ...'))

        for current, edge in enumerate(layer.getFeatures()):

            order = edges[edge.id()]

            feature = QgsFeature()
            feature.setGeometry(edge.geometry())
            feature.setAttributes(edge.attributes() + [
                order
            ])
            sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
