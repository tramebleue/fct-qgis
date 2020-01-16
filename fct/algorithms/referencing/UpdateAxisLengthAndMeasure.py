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

from collections import Counter, namedtuple

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
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
from ..util import appendUniqueField

Segment = namedtuple('Segment', ('fid', 'a', 'b', 'hack', 'measure', 'length'))

class UpdateAxisLengthAndMeasure(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Compute a new `measure` attribute
        as the distance of each link to the network outlet.

        This algorithm also sets the M coordinate of input geometries.
        When there are anabranches or parallel branches,
        diffluence nodes are attributed the maximum distance to outlet,
        so as to minimize overlap in M coordinate.

        Input must be a preprocessed, downslope directed stream network,
        with single part geometries.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'UpdateAxisLengthAndMeasure')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    HACK_FIELD = 'HACK_FIELD'
    MEASURE_FIELD = 'MEASURE_FIELD'

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
            self.HACK_FIELD,
            self.tr('Hack Order Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='HACK'))

        self.addParameter(QgsProcessingParameterField(
            self.MEASURE_FIELD,
            self.tr('Measure Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='MEASURE'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Updated'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        hack_field = self.parameterAsString(parameters, self.HACK_FIELD, context)
        measure_field = self.parameterAsString(parameters, self.MEASURE_FIELD, context)

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('AXIS', QVariant.Int, len=5), fields)
        appendUniqueField(QgsField('LAXIS', QVariant.Double, len=10, prec=2), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineStringZM,
            layer.sourceCrs())

        # Step 1 - Find sources and build adjacency index

        feedback.setProgressText(self.tr("Build network graph ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        graph = dict()
        segments = list()
        indegree = Counter()

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break


            a = feature.attribute(from_node_field)
            b = feature.attribute(to_node_field)
            hack = feature.attribute(hack_field)
            measure = feature.attribute(measure_field)

            segment = Segment(feature.id(), a, b, hack, measure, feature.geometry().length())
            segments.append(segment)
            graph[a] = segment
            indegree[b] += 1

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Output measured lines ..."))

        sources = sorted([node for node in graph if indegree[node] == 0], key=lambda f: (graph[f].hack, -graph[f].measure))
        current = 0

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

        for axis, source in enumerate(sources):

            axis_order = graph[source].hack
            axis_segments = list()
            node = source

            while node in graph:

                segment = graph[node]

                if segment.hack < axis_order:
                    break

                axis_segments.append(segment)
                node = segment.b

            axis_length = sum(s.length for s in axis_segments)

            for segment in axis_segments:

                query = QgsFeatureRequest(segment.fid)

                for feature in layer.getFeatures(query):

                    out_feature = QgsFeature()
                    out_feature.setGeometry(setM(feature.geometry(), segment.measure))
                    out_feature.setAttributes(feature.attributes() + [
                        axis+1,
                        axis_length
                    ])

                    sink.addFeature(out_feature)

                current += 1
                feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
