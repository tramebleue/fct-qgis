# -*- coding: utf-8 -*-

"""
MergeShortLinks - Merge links shorter than a given distance

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import Counter, defaultdict, namedtuple

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterString,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

Link = namedtuple('Link', ('a', 'b', 'feature_id', 'length', 'order'))

def create_link_index(adjacency, key):
    """ Index: key -> list of link corresponding to key
    """

    index = defaultdict(list)

    for link in adjacency:
        k = key(link)
        index[k].append(link)

    return index

class MergeShortLinks(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Merge links shorter than a given distance
        with their upstream parent, following Hack order.
        Also merge short source links with the preceding downstream link.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'MergeShortLinks')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    MERGED = 'MERGED'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    HACK_ORDER_FIELD = 'HACK_ORDER_FIELD'
    MIN_LENGTH = 'MIN_LENGTH'
    OUTPUT_GROUP_FIELD = 'OUTPUT_GROUP_FIELD'

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

        self.addParameter(QgsProcessingParameterField(
            self.HACK_ORDER_FIELD,
            self.tr('Hack Order Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='HACK'))

        self.addParameter(QgsProcessingParameterDistance(
            self.MIN_LENGTH,
            self.tr('Minimum Link Length'),
            parentParameterName=self.INPUT,
            defaultValue=5e3))

        self.addParameter(QgsProcessingParameterString(
            self.OUTPUT_GROUP_FIELD,
            self.tr('Output Group Field'),
            defaultValue='UGO'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Links To Groups'),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.MERGED,
            self.tr('Merged Links'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        order_field = self.parameterAsString(parameters, self.HACK_ORDER_FIELD, context)
        min_length = self.parameterAsDouble(parameters, self.MIN_LENGTH, context)
        group_field = self.parameterAsString(parameters, self.OUTPUT_GROUP_FIELD, context)

        fields = layer.fields().toList() + [
            QgsField(group_field, QVariant.Int)
        ]

        (sink, sink_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            asQgsFields(*fields),
            layer.wkbType(),
            layer.sourceCrs())

        (merged, merged_id) = self.parameterAsSink(
            parameters,
            self.MERGED,
            context,
            asQgsFields(
                QgsField(group_field, QVariant.Int),
                QgsField(order_field, QVariant.Int),
                QgsField(from_node_field, QVariant.Int),
                QgsField(to_node_field, QVariant.Int),
                QgsField('LENGTH', QVariant.Double)
            ),
            layer.wkbType(),
            layer.sourceCrs())

        # Step 1 - Find sources and build adjacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        adjacency = list()
        outdegree = Counter()
        indegree = Counter()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            order = edge.attribute(order_field)
            adjacency.append(Link(a, b, edge.id(), edge.geometry().length(), order))
            outdegree[a] += 1
            indegree[b] += 1

            feedback.setProgress(int(current * total))

        def key(link):
            """ Index by b node """
            return link.b

        # Index: b -> list of links connected to b
        edge_index = create_link_index(adjacency, key)

        # outlets = set([link.b for link in adjacency]) - set([link.a for link in adjacency])
        outlets = set(link.b for link in adjacency if outdegree[link.b] == 0)

        stack = list(outlets)

        feedback.setProgressText(self.tr("Find maximum distance from outlet ..."))

        current = 0
        group = 0
        merges = 0
        seen_nodes = set(outlets)
        output_links = set()
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        srclayer = context.getMapLayer(layer.sourceName())

        # start from outlets,
        # and traverse graph

        while stack:

            if feedback.isCanceled():
                break

            node = stack.pop()

            links = list(edge_index[node])

            while links:

                # check if link.a is a diffluence
                # if outdegree[link.a] > 1:
                #     outdegree[link.a] -= 1
                #     continue

                link = links.pop()
                current = current + 1

                if feedback.isCanceled():
                    break

                if link.feature_id in output_links:
                    continue

                group += 1
                downstream_node = link.b

                feature = srclayer.getFeature(link.feature_id)
                order = link.order
                merged_length = link.length
                merged_geometries = [feature.geometry()]
                next_link = link

                feature = srclayer.getFeature(link.feature_id)

                out_feature = QgsFeature()
                out_feature.setGeometry(feature.geometry())
                out_feature.setAttributes(
                    feature.attributes() + [group])
                sink.addFeature(out_feature)

                while merged_length < min_length:

                    if feedback.isCanceled():
                        break

                    # Find upstream link with same order

                    next_link = None

                    for upstream_link in edge_index[link.a]:

                        if upstream_link.order == order:

                            feature = srclayer.getFeature(upstream_link.feature_id)

                            merged_length += upstream_link.length
                            merged_geometries.append(feature.geometry())
                            merges += 1

                            out_feature = QgsFeature()
                            out_feature.setGeometry(feature.geometry())
                            out_feature.setAttributes(
                                feature.attributes() + [group])
                            sink.addFeature(out_feature)

                            next_link = upstream_link

                        else:

                            links.append(upstream_link)

                    if next_link:
                        link = next_link
                    else:
                        break

                upstream_node = link.a

                if next_link:

                    # merged_length >= min_length
                    # but there might remain a short link at network head.
                    # Look ahead in case we need to include source link

                    for upstream_link in edge_index[next_link.a]:

                        if indegree[upstream_link.a] == 0 and upstream_link.length < min_length:

                            feature = srclayer.getFeature(upstream_link.feature_id)

                            out_feature = QgsFeature()
                            out_feature.setGeometry(feature.geometry())
                            out_feature.setAttributes(
                                feature.attributes() + [group])
                            sink.addFeature(out_feature)
                            output_links.add(upstream_link.feature_id)

                            if upstream_link.order == order:

                                merged_length += upstream_link.length
                                merged_geometries.append(feature.geometry())
                                merges += 1
                                upstream_node = upstream_link.a

                # Output merged segments

                geometry = QgsGeometry.fromPolylineXY([
                    c for geom in reversed(merged_geometries)
                    for c in geom.asPolyline()])
                out_feature = QgsFeature()
                out_feature.setGeometry(geometry)
                out_feature.setAttributes([
                    group,
                    order,
                    upstream_node,
                    downstream_node,
                    geometry.length()
                ])
                merged.addFeature(out_feature)

                if link.a not in seen_nodes:
                    stack.append(link.a)
                    seen_nodes.add(link.a)

            feedback.setProgress(int(current * total))

        feedback.pushInfo('%d merges, %d links' % (merges, group))

        return {
            self.OUTPUT: sink_id,
            self.MERGED: merged_id
        }
