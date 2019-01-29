# -*- coding: utf-8 -*-

"""
Variable-Width Vertex-Wise Buffer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsVector,
    QgsWkbTypes
)

# def mparallel(geometry, factor=1.0):
#     """
#     Parallel line, CapFlat, JoinStyleMiter.
#     Returns list of QgsPoint.
#     """

#     points = list()

#     for i, vertex in enumerate(geometry.vertices()):

#         width = factor*vertex.m()
#         angle = geometry.angleAtVertex(i)

#         if i == 0:

#             point = QgsPoint(
#                 vertex.x() - width*math.cos(angle),
#                 vertex.y() + width*math.sin(angle))
#             points.append(point)
#             previous = vertex

#         else:

#             direction = QgsVector(
#                 vertex.x() - previous.x(),
#                 vertex.y() - previous.y())

#             bisector_direction = QgsVector(
#                 -math.cos(angle),
#                 math.sin(angle))

#             if abs(bisector_direction.angle(direction)) < 1e-4:

#                 direction = direction.normalized()
#                 point = QgsPoint(
#                     vertex.x() + width*direction.x(),
#                     vertex.y() + width*direction.y())

#                 if point != points[-1]:
#                     points.append(point)

#             else:

#                 intersects, point = QgsGeometryUtils.lineIntersection(
#                     points[-1], direction,
#                     vertex, bisector_direction)

#                 point = QgsPoint(point.x(), point.y())
#                 if intersects and point != points[-1]:
#                     points.append(point)

#             previous = vertex

#     return points

# def mbuffer(geometry):
#     """
#     LineString Buffer, CapFlat, JoinStyleMiter
#     Retunrs QgsGeometry, Polygon 2D

#     >>> g = QgsGeometry.fromWkt('LINESTRING(0 0 0 1, 0 1 0 1, 1 1 0 1, 2 2 0 1, 3 1 0 1, 4 2 0 1, 3 3 0 1)')
#     """

#     points = mparallel(geometry, 1.0)
#     points.extend(reversed(mparallel(geometry, -1.0)))
#     points.append(points[0])

#     union = QgsGeometry.unaryUnion([QgsGeometry(QgsLineString(points))])
#     return QgsGeometry.polygonize([union])

def buffer_by_m_round(geometry):
    """
    CapFlat, JoinStyleRound
    """

    parts = list()
    previous = None
    previous_width = 0.0

    for i, vertex in enumerate(geometry.vertices()):

        width = vertex.m()

        if i > 0:

            direction = QgsVector(
                previous.y() - vertex.y(),
                vertex.x() - previous.x()).normalized()

            p1 = QgsPointXY(
                previous.x() - previous_width*direction.x(),
                previous.y() - previous_width*direction.y())

            p2 = QgsPointXY(
                previous.x() + previous_width*direction.x(),
                previous.y() + previous_width*direction.y())

            p3 = QgsPointXY(
                vertex.x() + width*direction.x(),
                vertex.y() + width*direction.y())

            p4 = QgsPointXY(
                vertex.x() - width*direction.x(),
                vertex.y() - width*direction.y())

            parts.append(QgsGeometry.fromPolygonXY([[p1, p2, p3, p4, p1]]))

            parts.append(QgsGeometry.fromPointXY(
                QgsPointXY(vertex.x(), vertex.y())
            ).buffer(width, 12))

        previous = vertex
        previous_width = width

    parts.pop()

    return QgsGeometry.unaryUnion(parts)

def buffer_by_m_miter(geometry):
    """
    CapFlat, JoinStyleMiter
    """

    parts = list()

    for i, vertex in enumerate(geometry.vertices()):

        if i == 0:
            continue

        angle0 = geometry.angleAtVertex(i-1)
        angle1 = geometry.angleAtVertex(i)
        previous = geometry.vertexAt(i-1)

        direction = QgsVector(
            previous.y() - vertex.y(),
            vertex.x() - previous.x()).normalized()

        bisector0 = QgsVector(
            -math.cos(angle0),
            math.sin(angle0))
        bisector1 = QgsVector(
            -math.cos(angle1),
            math.sin(angle1))

        alpha0 = bisector0.angle(direction)
        alpha1 = bisector1.angle(direction)

        if i == 1:

            if math.cos(alpha0) < 0.5:

                width = 2*previous.m()

                p1 = QgsPointXY(
                    previous.x() - width*direction.x() + width*direction.y(),
                    previous.y() - width*direction.y() - width*direction.x())

                p2 = QgsPointXY(
                    previous.x() - width*direction.x() - width*direction.y(),
                    previous.y() - width*direction.y() + width*direction.x())

            else:

                width0 = previous.m() / math.cos(alpha0)

                p1 = QgsPointXY(
                    previous.x() - width0*bisector0.x(),
                    previous.y() - width0*bisector0.y())

                p2 = QgsPointXY(
                    previous.x() + width0*bisector0.x(),
                    previous.y() + width0*bisector0.y())

        if math.cos(alpha1) < 0.5:

            width = 2*vertex.m()

            p3 = QgsPointXY(
                previous.x() + width*direction.x() - width*direction.y(),
                previous.y() + width*direction.y() + width*direction.x())

            p4 = QgsPointXY(
                previous.x() + width*direction.x() + width*direction.y(),
                previous.y() + width*direction.y() - width*direction.x())

        else:

            width1 = vertex.m() / math.cos(alpha1)

            p3 = QgsPointXY(
                vertex.x() + width1*bisector1.x(),
                vertex.y() + width1*bisector1.y())

            p4 = QgsPointXY(
                vertex.x() - width1*bisector1.x(),
                vertex.y() - width1*bisector1.y())

        parts.append(QgsGeometry.fromPolygonXY([[p1, p2, p3, p4, p1]]))
        p1 = p4
        p2 = p3

    return QgsGeometry.unaryUnion(parts)

from ..metadata import AlgorithmMetadata

class LineStringBufferByM(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Variable-Width Vertex-Wise Buffer.
    Local buffer width at each vertex is determined from M coordinate.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LineStringBufferByM')

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('LineString Buffer')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, 'INPUT', context)

        if not QgsWkbTypes.hasZ(layer.wkbType()):
            feedback.reportError(self.tr('Input must have Z coordinate.'), True)
            return False

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        features = []

        for geometry in feature.geometry().asGeometryCollection():

            new_geometry = buffer_by_m_round(geometry)
            new_feature = QgsFeature()
            new_feature.setAttributes(feature.attributes())
            new_feature.setGeometry(new_geometry)
            features.append(new_feature)

        return features
