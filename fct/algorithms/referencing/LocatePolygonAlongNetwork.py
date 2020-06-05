# -*- coding: utf-8 -*-

"""
Locate Polygon Along Linear Reference Network

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import (
    QVariant
)

from qgis.core import (
    QgsApplication,
    QgsExpression,
    QgsGeometry,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPoint,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

def nearest_point_on_linestring(linestring, point, vertex):
    """
    Search for nearest point on linestring,
    given nearest vertex index.

    Returns
    -------

    before: int
        before vertex index

    distance: float
        distance from before vertex on nearest segment

    nearest: QgsPointXY
        nearest point on segment
    """

    point_geometry = QgsGeometry.fromPointXY(point)

    if vertex == 0:
        nearest_segment = QgsGeometry.fromPolylineXY(linestring[vertex:vertex+2])
        before = vertex

    elif vertex == len(linestring) - 1:
        nearest_segment = QgsGeometry.fromPolylineXY(linestring[vertex-1:vertex+1])
        before = vertex-1

    else:

        segment_before = QgsGeometry.fromPolylineXY(linestring[vertex-1:vertex+1])
        segment_after = QgsGeometry.fromPolylineXY(linestring[vertex:vertex+2])

        if point_geometry.distance(segment_before) < point_geometry.distance(segment_after):

            nearest_segment = segment_before
            before = vertex-1

        else:

            nearest_segment = segment_after
            before = vertex

    nearest_point = nearest_segment.nearestPoint(point_geometry)

    return before, point_geometry.distance(nearest_point), nearest_point.asPoint()

class LocatePolygonAlongNetwork(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Calculate linear referencing coordinate (axis, measure) for each input polygon
    using the given oriented, measured, hierarchical line network.
    When the polygon intersects several axes, the most important axis is selected.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LocatePolygonAlongNetwork')

    LINEAR_REFERENCE = 'LINEAR_REFERENCE'
    AXIS_PK_FIELD = 'AXIS_ID_FIELD'
    AXIS_PRIORITY_FIELD = 'AXIS_PRIORITY_FIELD'

    def initParameters(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LINEAR_REFERENCE,
            self.tr('Linear Reference Network'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.AXIS_PK_FIELD,
            self.tr('Axis Primary Key'),
            parentLayerParameterName=self.LINEAR_REFERENCE,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterField(
            self.AXIS_PRIORITY_FIELD,
            self.tr('Axis Priority Field'),
            parentLayerParameterName=self.LINEAR_REFERENCE,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='HACK'))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorPolygon]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Polygon Location')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring
        return inputWkbType

    def outputFields(self, inputFields): #pylint: disable=no-self-use,missing-docstring
        appendUniqueField(QgsField('AXIS', QVariant.Int), inputFields)
        appendUniqueField(QgsField('LOCM', QVariant.Double), inputFields)
        return inputFields

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring,unused-argument
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        ref_layer = self.parameterAsSource(parameters, self.LINEAR_REFERENCE, context)
        axis_pk_field = self.parameterAsString(parameters, self.AXIS_PK_FIELD, context)
        axis_priority_field = self.parameterAsString(parameters, self.AXIS_PRIORITY_FIELD, context)

        if not QgsWkbTypes.hasM(ref_layer.wkbType()):
            feedback.reportError(self.tr('Linear reference must have M coordinate.'), True)
            return False

        feedback.setProgressText('Build reference point index')
        total = 100.0 / ref_layer.featureCount() if ref_layer.featureCount() else 0
        temp_uri = "point?crs=%s&field=gid:integer&field=axis:integer&field=priority:double&field=vertex:integer" % ref_layer.sourceCrs().authid().lower()
        temp_layer = QgsVectorLayer(temp_uri, "RefPointsX", "memory")
        temp_layer.startEditing()
        gid = 1

        for current, feature in enumerate(ref_layer.getFeatures()):

            if feedback.isCanceled():
                return False

            feedback.setProgress(int(current*total))

            axis = feature.id()
            priority = float(feature.attribute(axis_priority_field))

            for current_vertex, vertex in enumerate(feature.geometry().asPolyline()):
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPointXY(vertex))
                feature.setAttributes([
                    gid,
                    axis,
                    priority,
                    current_vertex
                ])
                temp_layer.addFeature(feature)
                gid += 1

        temp_layer.commitChanges()

        self.ref_layer = ref_layer
        self.axis_pk_field = axis_pk_field
        self.axis_priority_field = axis_priority_field
        self.index_layer = temp_layer
        self.nearest_index = QgsSpatialIndex(temp_layer.getFeatures())

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        geometry = feature.geometry()
        centroid = geometry.pointOnSurface()
        request = QgsFeatureRequest().setFilterFids(
            self.nearest_index.intersects(geometry.boundingBox()))
        features = list()

        nearest_distance = float('inf')
        nearest_priority = float('inf')
        nearest = None
        count = 0

        for candidate in self.index_layer.getFeatures(request):

            priority = candidate.attribute('priority')
            distance = candidate.geometry().distance(centroid)

            if priority < nearest_priority:

                nearest = candidate
                nearest_priority = priority
                nearest_distance = distance

            elif priority == nearest_priority and distance < nearest_distance:

                nearest = candidate
                nearest_distance = distance

            count += 1

        # feedback.pushInfo('Checked %d candidates' % count)

        if nearest:

            axis = nearest.attribute('axis')
            vertex = nearest.attribute('vertex')
            axis_feature = [f for f in self.ref_layer.getFeatures(QgsFeatureRequest().setFilterFids([axis]))][0]
            axis_geometry = axis_feature.geometry()

            before_vertex, distance, nearest_point = nearest_point_on_linestring(axis_geometry.asPolyline(), centroid.asPoint(), vertex)

            point_before = axis_geometry.vertexAt(before_vertex)
            point_after = axis_geometry.vertexAt(before_vertex+1)
            segment_length = point_after.distance(point_before)

            if segment_length > 0:

                # z = point_before.z() + (point_after.z() - point_before.z()) * distance / segment_length
                m = point_before.m() + (point_after.m() - point_before.m()) * distance / segment_length

            else:

                # z = point_before.z()
                m = point_before.m()

            # location = QgsPoint(centroid.x(), centroid.y(), z, m)
            # geometry = QgsGeometry(location)
            transformed = QgsFeature()
            transformed.setGeometry(geometry)
            transformed.setAttributes(
                feature.attributes() + [
                    axis_feature.attribute(self.axis_pk_field),
                    m
                ])

            features.append(transformed)

        return features
