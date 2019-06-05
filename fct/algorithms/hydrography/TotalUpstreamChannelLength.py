# -*- coding: utf-8 -*-

"""
UpstreamChannelLength - Compute a new `UCL` attribute
    as the total upstream channel length of each link.

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict, deque

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber
)

# from .graph import create_link_index
from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

class TotalUpstreamChannelLength(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute the total upstream channel length of each link;
    and store the result in a new attribute named `TUCL`.
    The current implementation does not handle the presence of diffluences
    in the stream network.
    If needed, you can use the `Principal Stem` tool
    to extract a simpler network.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'TotalUpstreamChannelLength')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    SCALE = 'SCALE'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream Network'),
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

        self.addParameter(QgsProcessingParameterNumber(
            self.SCALE,
            self.tr('Scale Factor'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.001))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Total Upstream Channel Length'),
            QgsProcessing.TypeVectorLine))

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     "CONVERGING",
        #     self.tr('Converging Nodes'),
        #     QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        scale = self.parameterAsDouble(parameters, self.SCALE, context)

        fields = layer.fields().toList() + [
            QgsField('TUCL', QVariant.Double)
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            asQgsFields(*fields),
            layer.wkbType(),
            layer.sourceCrs())

        # Step 1 - Find sources and build adjacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        # adjacency = list()

        # Directed graph: node A -connects to-> list of nodes B
        graph = defaultdict(set)
        backtrack = defaultdict(set)
        contributions = defaultdict(lambda: 0)

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)

            length = edge.geometry().length()
            contributions[b] += length
            graph[a].add(b)
            backtrack[b].add(a)

            feedback.setProgress(int(current * total))

        # diffluences = {a for a in graph if len(graph[a]) > 1}
        sources = {a for a in graph if len(backtrack[a]) == 0}
        # outlets = {b for b in backtrack if len(graph[b]) == 0}

        feedback.setProgressText(self.tr("Accumulate ..."))

        tucl = defaultdict(lambda: 0.0)

        queue = deque(sources)
        # seen_nodes = set()
        visited = 0

        indegree = defaultdict(lambda: 0)
        indegree.update({a: len(backtrack[a]) for a in backtrack})

        while queue:

            if feedback.isCanceled():
                break

            a = queue.popleft()
            visited += 1

            indegree[a] -= 1

            if indegree[a] > 0:
                continue

            tucl[a] = contributions[a]
            for up in backtrack[a]:
                tucl[a] += tucl[up]

            queue.extend(graph[a])

        feedback.setProgressText(self.tr("Output features ..."))

        # feedback.pushInfo('Terminal nodes : %d' % len(terminal_nodes))
        feedback.pushInfo('Visited nodes : %d' % visited)

        current = 0
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            ucl = tucl[a] + edge.geometry().length()

            out_feature = QgsFeature()
            out_feature.setGeometry(edge.geometry())
            out_feature.setAttributes(edge.attributes() + [
                scale*ucl
            ])

            sink.addFeature(out_feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
