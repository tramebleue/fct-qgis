# -*- coding: utf-8 -*-

"""
Buffer By M Coordinate
Miter-style buffers need more love and tests.

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
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointXY,
    QgsVector
)

def buffer_by_m_round(geometry):
    """
    CapFlat, JoinStyleRound
    """

    parts = list()
    previous = None
    previous_width = 0.0

    for i, vertex in enumerate(geometry.vertices()):

        width = 0.5*vertex.m()

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

def miter_join(origin, bisector, direction, width, miter_limit):

    alpha = 0.5*math.pi - bisector.angle(direction)

    if abs(math.cos(alpha)) < (1.0 / miter_limit):

        beta = abs(bisector.angle(direction))
        if beta > 0.5*math.pi:
            beta = abs(math.pi - beta)

        width1 = miter_limit*width
        width2 = (1 - miter_limit*beta)*width

        p2 = QgsPointXY(
            origin.x() - width1*bisector.x() + width2*bisector.y(),
            origin.y() - width1*bisector.y() - width2*bisector.x())

        p1 = QgsPointXY(
            origin.x() - width1*bisector.x() - width2*bisector.y(),
            origin.y() - width1*bisector.y() + width2*bisector.x())

    else:

        width0 = width / abs(math.cos(alpha))

        p1 = QgsPointXY(
            origin.x() - width0*bisector.x(),
            origin.y() - width0*bisector.y())

        p2 = QgsPointXY(
            origin.x() + width0*bisector.x(),
            origin.y() + width0*bisector.y())

    return p1, p2


def directionAt(geometry, i):

    previous = geometry.vertexAt(i-1)
    vertex = geometry.vertexAt(i)

    return QgsVector(
        vertex.x() - previous.x(),
        vertex.y() - previous.y()).normalized()

def bisectorAt(geometry, i):

    angle = geometry.angleAtVertex(i)
    return QgsVector(-math.cos(angle), math.sin(angle))

def buffer_by_m_miter(geometry, miter_limit=2):
    """
    CapFlat, JoinStyleMiter
    """

    parts = list()

    for i, vertex in enumerate(geometry.vertices()):

        if i == 0:
            continue

        previous = geometry.vertexAt(i-1)

        direction = QgsVector(
            vertex.x() - previous.x(),
            vertex.y() - previous.y()).normalized()

        if i == 1:

            bisector = bisectorAt(geometry, i-1)
            p1, p2 = miter_join(previous, bisector, direction, 0.5*previous.m(), miter_limit)

        bisector = bisectorAt(geometry, i)
        p4, p3 = miter_join(vertex, bisector, direction, 0.5*vertex.m(), miter_limit)

        part = QgsGeometry.fromPolygonXY([[p1, p2, p3, p4, p1]])
        parts.append(part)

        p1 = p4
        p2 = p3

    if len(parts) == 1:
        return parts[0]

    return QgsGeometry.unaryUnion(parts)

def test():

    def zm(p, z=0.0, m=0.0):
        return QgsPoint(p.x(), p.y(), z, m)

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 1 0)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))
    miter_join(l1m.vertexAt(0), bisectorAt(l1m, 0), directionAt(l1m, 1), 0.05, 2)

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 0 1)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 1 1)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 1 0, 2 0)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 1 1, 2 0)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))

    l1 = QgsGeometry.fromWkt('LINESTRING(0 0, 10 0.1, 0 0.2)')
    l1m = QgsGeometry(QgsLineString([zm(p, m=0.2) for p in l1.vertices()]))



