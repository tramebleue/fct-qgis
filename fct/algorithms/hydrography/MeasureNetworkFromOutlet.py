# -*- coding: utf-8 -*-

"""
MeasureNetworkFromOutlet - Compute a new `measure` attribute
    as the distance of each link to the network outlet.

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
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes
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

class MeasureNetworkFromOutlet(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Compute a new `measure` attribute
        as the distance of each link to the network outlet.

        This algorithm also sets the M coordinate of input geometries.
        When there are anabranches or parallel branches,
        diffluence nodes are attributed the maximum distance to outlet,
        so as to minimize overlap in M coordinate.

        Input must be a preprocessed, downslope directed stream network,
        with single part geometries.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'MeasureNetworkFromOutlet')

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
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Measured Links'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        fields = layer.fields().toList() + [
            QgsField('MEASURE', QVariant.Double, len=10, prec=2),
            QgsField('LENGTH', QVariant.Double, len=6, prec=2)
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            asQgsFields(*fields),
            QgsWkbTypes.LineStringZM,
            layer.sourceCrs())

        # Step 1 - Find sources and build adjacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        adjacency = list()
        outdegree = Counter()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append(Link(a, b, edge.id(), edge.geometry().length()))
            outdegree[a] += 1

            feedback.setProgress(int(current * total))

        def key(link):
            """ Index by b node """
            return link.b

        # Index: b -> list of links connected to b
        edge_index = create_link_index(adjacency, key)

        # outlets = set([link.b for link in adjacency]) - set([link.a for link in adjacency])
        outlets = set(link.b for link in adjacency if outdegree[link.b] == 0)

        measures = {node: 0.0 for node in outlets}
        stack = list(outlets)

        feedback.setProgressText(self.tr("Find maximum distance from outlet ..."))

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
            measure = measures[node]

            # traverse graph until next diffluence

            for link in edge_index[node]:

                measure_a = measures.get(link.a, 0.0)

                if measure_a < measure + link.length:
                    measures[link.a] = measure + link.length

                # check if link.a is a diffluence
                if outdegree[link.a] > 1:
                    outdegree[link.a] -= 1
                    continue

                # otherwise process upward
                stack.append(link.a)

            current = current + 1
            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Output measured lines ..."))

        def setM(geometry, origin):
            """ Set M coordinate along polyline.
                Input geometry is assumed to be a simple linestring
                (no multipart)
            """

            if geometry.isMultipart():
                raise QgsProcessingException(
                    self.tr('Input layer must not contain multipart geometries'))

            points = list()
            measure = origin + geometry.length()
            previous = None

            for point in geometry.vertices():
                if previous:
                    measure -= previous.distance(point)
                points.append(QgsPoint(point.x(), point.y(), point.z(), m=measure))
                previous = point

            return QgsGeometry.fromPolyline(points)

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            b = edge.attribute(to_node_field)
            measure = measures.get(b, 0.0)
            length = edge.geometry().length()

            out_feature = QgsFeature()
            out_feature.setGeometry(setM(edge.geometry(), measure))
            out_feature.setAttributes(edge.attributes() + [
                measure,
                length
            ])

            sink.addFeature(out_feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
