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

from collections import defaultdict, Counter, namedtuple

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
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

Link = namedtuple('Link', ('a', 'b', 'edge_id', 'length'))

def create_link_index(adjacency, key):
    """ Index: key -> list of link corresponding to key
    """

    index = defaultdict(list)

    for link in adjacency:
        k = key(link)
        index[k].append(link)

    return index

class UpstreamChannelLength(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Compute a new `UCL` attribute
        as the total upstream channel length of each link.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'UpstreamChannelLength')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream Network'),
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
            self.tr('Upstream Channel Length'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        fields = layer.fields().toList() + [
            QgsField('UCL', QVariant.Double, len=10, prec=2)
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
        adjacency = list()
        indegree = Counter()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append(Link(a, b, edge.id(), edge.geometry().length()))
            indegree[b] += 1

            feedback.setProgress(int(current * total))

        sources = set([link.a for link in adjacency]) - set([link.b for link in adjacency])

        def key(link):
            """ Index by a node """
            return link.a

        # Index: a -> list of links departing from a, downslope walk
        edge_index = create_link_index(adjacency, key)

        stack = list(sources)
        distances = {source: 0.0 for source in sources}

        feedback.setProgressText(self.tr("Accumulate ..."))

        current = 0
        # seen_nodes = set()
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        while stack:

            if feedback.isCanceled():
                break

            node = stack.pop()
            ucl = distances[node]

            for link in edge_index[node]:

                if indegree[link.b] > 0:

                    distances[link.b] = distances.get(link.b, 0.0) + ucl + link.length
                    indegree[link.b] -= 1

                    # check if we reach a confluence cell
                    if indegree[link.b] > 0:
                        continue

                    stack.append(link.b)

                # if not link.b in seen_nodes:
                #     seen_nodes.add(link.b)
                #     stack.append(link.b)

            current = current + 1
            feedback.setProgress(int(current * total))

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            b = edge.attribute(to_node_field)
            ucl = distances.get(b, 0.0)

            out_feature = QgsFeature()
            out_feature.setGeometry(edge.geometry())
            out_feature.setAttributes(edge.attributes() + [
                ucl
            ])

            sink.addFeature(out_feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
