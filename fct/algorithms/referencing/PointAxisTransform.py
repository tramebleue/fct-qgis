# -*- coding: utf-8 -*-

"""
Axis Transform

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
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsLineString,
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

def signed_distance(a, b, c):
    """
    Return the signed distance from point C to segment [AB]

    a, b, c: QgsPoint
    """

    ab = QgsPointXY(b) - QgsPointXY(a)
    ac = QgsPointXY(c) - QgsPointXY(a)
    length_ab = ab.length()

    return ab.crossProduct(ac) / length_ab if length_ab > 0.0 else ac.length()

class PointAxisTransform(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Calculate linear referencing coordinate (axis, measure) for each input point
    using the given oriented and measured line network.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'PointAxisTransform')

    LINEAR_REFERENCE = 'LINEAR_REFERENCE'
    AXIS_PK_FIELD = 'AXIS_ID_FIELD'

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

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorPoint]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transformed')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring
        return QgsWkbTypes.addM(inputWkbType)

    def outputFields(self, inputFields): #pylint: disable=no-self-use,missing-docstring
        appendUniqueField(QgsField('RX', QVariant.Double), inputFields)
        appendUniqueField(QgsField('RY', QVariant.Double), inputFields)
        return inputFields

    # def outputCrs(self, inputCrs): #pylint: disable=no-self-use,missing-docstring,unused-argument
    #     return QgsCoordinateReferenceSystem.fromEpsgId(6505)

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring,unused-argument
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, 'INPUT', context)
        ref_layer = self.parameterAsSource(parameters, self.LINEAR_REFERENCE, context)
        axis_pk_field = self.parameterAsString(parameters, self.AXIS_PK_FIELD, context)

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('MultiLineString are not supported'), True)
            return False

        if not QgsWkbTypes.hasM(ref_layer.wkbType()):
            feedback.reportError(self.tr('Linear reference must have M coordinate.'), True)
            return False

        self.ref_layer = ref_layer
        self.axis_pk_field = axis_pk_field
        # self.index_layer = temp_layer
        self.nearest_index = QgsSpatialIndex(ref_layer.getFeatures())

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        geometry = feature.geometry()
        point = geometry.vertexAt(0)

        pointxy = QgsPointXY(point)
        request = QgsFeatureRequest().setFilterFids(self.nearest_index.nearestNeighbor(pointxy, 10))
        min_distance = float('inf')
        nearest = None

        for candidate in self.ref_layer.getFeatures(request):

            distance = candidate.geometry().distance(geometry)
            if distance < min_distance:
                min_distance = distance
                nearest = candidate.geometry()

        if nearest:

            point_before = nearest.vertexAt(0)
            point_after = nearest.vertexAt(1)
            # nearest_point = nearest.nearestPoint(geometry)
            measure = nearest.lineLocatePoint(geometry)

            x = point_before.m() + (point_after.m() - point_before.m()) * measure / nearest.length()
            y = signed_distance(point_before, point_after, point)

            transformed = QgsFeature()
            transformed.setAttributes(feature.attributes() + [
                x,
                y
            ])
            transformed.setGeometry(geometry)

            return [transformed]

        else:

            return []
