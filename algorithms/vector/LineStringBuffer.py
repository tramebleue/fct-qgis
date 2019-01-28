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
    QgsGeometryUtils,
    QgsLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsVector,
    QgsWkbTypes
)

def mparallel(geometry, factor=1.0):
    """
    Parallel line, CapFlat, JoinStyleMiter.
    Returns list of QgsPoint.
    """

    points = list()

    for i, vertex in enumerate(geometry.vertices()):

        width = factor*vertex.m()
        angle = geometry.angleAtVertex(i)

        if i == 0:

            point = QgsPoint(
                vertex.x() - width*math.cos(angle),
                vertex.y() + width*math.sin(angle))
            points.append(point)
            previous = vertex

        else:

            direction = QgsVector(
                vertex.x() - previous.x(),
                vertex.y() - previous.y())

            bisector_direction = QgsVector(
                -math.cos(angle),
                math.sin(angle))

            if abs(bisector_direction.angle(direction)) < 1e-4:

                direction = direction.normalized()
                point = QgsPoint(
                    vertex.x() + width*direction.x(),
                    vertex.y() + width*direction.y())

                if point != points[-1]:
                    points.append(point)

            else:

                intersects, point = QgsGeometryUtils.lineIntersection(
                    points[-1], direction,
                    vertex, bisector_direction)

                point = QgsPoint(point.x(), point.y())
                if intersects and point != points[-1]:
                    points.append(point)

            previous = vertex

    return points

def mbuffer(geometry):
    """
    LineString Buffer, CapFlat, JoinStyleMiter
    Retunrs QgsGeometry, Polygon 2D

    >>> g = QgsGeometry.fromWkt('LINESTRING(0 0 0 1, 0 1 0 1, 1 1 0 1, 2 2 0 1, 3 1 0 1, 4 2 0 1, 3 3 0 1)')
    """

    points = mparallel(geometry, 1.0)
    points.extend(reversed(mparallel(geometry, -1.0)))
    points.append(points[0])

    union = QgsGeometry.unaryUnion([QgsGeometry(QgsLineString(points))])
    return QgsGeometry.polygonize([union])

from ..metadata import AlgorithmMetadata

class LineStringBuffer(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Variable-Width Vertex-Wise Buffer.
    Local buffer width at each vertex is determined from M coordinate.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LineStringBuffer')

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

            new_geometry = mbuffer(geometry)

            for part in new_geometry.asGeometryCollection():
                new_feature = QgsFeature()
                new_feature.setAttributes(feature.attributes())
                geom = QgsGeometry(part.clone())
                print(geom)
                new_feature.setGeometry(geom)
                features.append(new_feature)

        return features
