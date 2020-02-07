# -*- coding: utf-8 -*-

"""
Fix Network Connectivity

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
from ..util import appendUniqueField

class FixNetworkConnectivity(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    DOCME
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FixNetworkConnectivity')

    INPUT = 'INPUT'
    SUBSET = 'SUBSET'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    COPYFIELDS = 'COPYFIELDS'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Full Stream Network (Polylines)'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.SUBSET,
            self.tr('Subset From Input Network'),
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

        # self.addParameter(QgsProcessingParameterField(
        #     self.COPYFIELDS,
        #     self.tr('Copy Selected Fields to Output'),
        #     parentLayerParameterName=self.INPUT,
        #     type=QgsProcessingParameterField.Any))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Fixed Network'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        subset = self.parameterAsSource(parameters, self.SUBSET, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        # copy_fields = self.parameterAsFields(parameters, self.COPYFIELDS, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            subset.fields(),
            subset.wkbType(),
            subset.sourceCrs())

        feedback.setProgressText(self.tr("Build network graph ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        graph1 = defaultdict(list)
        indegree1 = Counter()

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = feature.attribute(from_node_field)
            b = feature.attribute(to_node_field)

            graph1[a].append((b, feature.geometry().length(), feature.id()))
            indegree1[b] += 1

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Build subset graph ..."))

        total = 100.0 / subset.featureCount() if subset.featureCount() else 0
        graph2 = defaultdict(list)
        indegree2 = Counter()

        for current, feature in enumerate(subset.getFeatures()):

            if feedback.isCanceled():
                break

            a = feature.attribute(from_node_field)
            b = feature.attribute(to_node_field)

            graph2[a].append(b)
            indegree2[b] += 1

            sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Find shortest path from dangling outlets ..."))

        outlets1 = [node for node in indegree1 if node not in graph1]
        outlets2 = [node for node in indegree2 if node not in graph2]
        tobefixed = set(outlets2) - set(outlets1)
        emitted = set()

        total = 100.0 / len(tobefixed) if tobefixed else 0

        for current, origin in enumerate(tobefixed):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current * total))

            queue = list()
            distance = dict()
            backtrack = dict()
            junction = None
            mindist = float('inf')

            heappush(queue, (0.0, origin, None, None))
            distance[origin] = 0.0

            while queue:

                dist, node, preceding, edge = heappop(queue)

                if node in distance and distance[node] < dist:
                    continue

                distance[node] = dist

                if preceding is not None:
                    backtrack[node] = (preceding, edge)

                if node in graph2:

                    if dist < mindist:

                        junction = node
                        mindist = dist

                else:

                    for next_node, next_length, edge in graph1[node]:

                        next_dist = dist + next_length

                        if next_node in distance:
                            if next_dist < distance[next_node]:
                                distance[next_node] = next_dist
                                heappush(queue, (next_dist, next_node, node, edge))
                        else:
                            distance[next_node] = next_dist
                            heappush(queue, (next_dist, next_node, node, edge))

            if junction is not None:

                path = list()
                node = junction

                while True:

                    node, edge = backtrack.get(node, (None, None))
                    if node is None:
                        break
                    else:
                        path.append(edge)

                query = QgsFeatureRequest(path)
                for feature in layer.getFeatures(query):
                    if feature.id() not in emitted:
                        emitted.add(feature.id())
                        sink.addFeature(feature)

        return {self.OUTPUT: dest_id}
