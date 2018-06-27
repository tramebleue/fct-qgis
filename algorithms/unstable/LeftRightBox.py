# -*- coding: utf-8 -*-

"""
***************************************************************************
    LeftRightBox.py
    ---------------------
    Date                 : May 2018
    Copyright            : (C) 2018 by Christophe Rousson
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Christophe Rousson'
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsVector, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from ...core import vector as vector_helper
from math import degrees, atan2
import numpy as np

def sign(x):
    if x == 0:
        return 0
    elif x > 0:
        return 1
    else:
        return -1

def side_of_line(o, a, b):
    """
    Parameters
    ----------

    o, a, b: QgsPoint

    Returns
    -------

    -1 if B is right to OA,
     1 if B is left to OA,
     0 if O, A and B are colinear
    """

    ax = a.x() - o.x()
    ay = a.y() - o.y()
    bx = b.x() - o.x()
    by = b.y() - o.y()
    cross = (ax * by) - (ay * bx)

    return sign(cross)

def segment_angle(a, b):
    """
    Parameters
    ----------

    a, b: QgsPoint

    Returns
    -------

    Angle of segment [A, B] with x axis
    """

    # return degrees(QgsVector(b.x() - a.x(), b.y() - a.y()).angle(QgsVector(1, 0)))
    return degrees(atan2(b.y() - a.y(), b.x() - a.x()))

def minimum_oriented_boundingbox(geom):

    hull = geom.convexHull()
    if hull.type() != QGis.Polygon:
        return QgsGeometry.fromRect(geom.boundingBox())

    exterior = hull.asPolygon()[0]
    p0 = QgsPoint(exterior[0])
    min_area = QgsGeometry.fromRect(hull.boundingBox()).area()
    min_box = None

    for i, p in enumerate(exterior[:-1]):

        angle = segment_angle(p, exterior[i+1])
        x = QgsGeometry(hull)
        x.rotate(angle, p0)
        box = QgsGeometry.fromRect(x.boundingBox())
        area = box.area()

        if area < min_area:

            min_area = area
            box.rotate(-angle, p0)
            min_box = box

    return min_box

def rotate_list(x, n):

    r = x[n:]
    r.extend(x[:n])
    return r

class LeftRightBoxDescriptor(object):
    """ LeftRightBox descriptor of the geometry `geom`.
    The left-right orientation in 2D space
    is defined with respect to the given reference point `outlet`.

     left hand side
    C2----- B -----C1
    |       |      |
    C--------------A --> downstream_point, axangle direction
    |       |      |
    C3----- D -----C0
     right hand side

    - C0,C1,C2,C3 = minimum oriented bounding box
    - A,B,C,D = box side midpoints
    - axis_a = [C, A]
    - axis_b = [B, D]
    - length = distance(C, A)
    - width = distance(B, D)
    """

    def __init__(self, geom, upstream_point, downstream_point, axangle):
        """
        Parameters
        ----------

        geom: QgsGeometry, Polygon
        outlet: QgsPoint

        Returns
        -------

        LeftRightBox descriptor of `geom`,
        given reference point `outlet`
        """

        minbox = minimum_oriented_boundingbox(geom)
        exterior = minbox.asPolygon()[0]

        # Find side midpoint closest to outlet
        # distance, nearest_point, vertex = minbox.closestSegmentWithContext(outlet)
        vertex = -1

        midpoints = []
        corners = []

        # Find cardinal points
        for i in range(0, 4):

            v0 = (vertex + i - 1) % 4
            v1 = (vertex + i) % 4
            segment = QgsGeometry.fromPolyline([ exterior[v0], exterior[v1] ])
            midpoint = segment.interpolate(0.5 * segment.length())
            midpoints.append(midpoint.asPoint())
            corners.append(exterior[v0])

        midpoints, corners, tie_angle = self.rotate_by_angle(midpoints, corners, axangle)
        if tie_angle < 30.0:
            midpoints, corners = self.rotate_by_points(midpoints, corners, upstream_point, downstream_point)

        self.minbox = minbox
        self.midpoints = midpoints
        self.corners = corners

    def rotate_by_points(self, midpoints, corners, upstream_point, downstream_point):

        minimum_distance = float('inf')
        min_midpoints = None
        min_corners = None

        for i in range(4):

            current_corners = rotate_list(corners, i)
            updist = QgsGeometry.fromPolyline([ current_corners[2], current_corners[3] ]).distance(QgsGeometry.fromPoint(upstream_point))
            downdist = QgsGeometry.fromPolyline([ current_corners[0], current_corners[1] ]).distance(QgsGeometry.fromPoint(downstream_point))
            distance = updist + downdist

            if distance < minimum_distance:

                minimum_distance = distance
                min_corners = current_corners
                min_midpoints = rotate_list(midpoints, i)

        return min_midpoints, min_corners

    def rotate_by_angle(self, midpoints, corners, axis_angle):

        minimum_angle = tie_angle = float('inf')
        min_midpoints = None
        min_corners = None

        for i in range(4):

            current_midpoints = rotate_list(midpoints, i)
            angle = segment_angle(current_midpoints[2], current_midpoints[0])

            diff_angle = angle - axis_angle

            while diff_angle < -180: diff_angle = diff_angle + 360
            while diff_angle > 180: diff_angle = diff_angle - 360

            diff_angle = abs(diff_angle)

            if diff_angle < minimum_angle:

                tie_angle = minimum_angle
                minimum_angle = diff_angle
                min_midpoints = current_midpoints
                min_corners = rotate_list(corners, i)

            elif diff_angle < tie_angle:

                tie_angle = diff_angle

        return min_midpoints, min_corners, tie_angle - minimum_angle

    def minimumBox(self):
        """ Minimum oriented bounding box
        """

        return self.minbox

    def rightBox(self):
        """ Right hand side half of minimum oriented bounding box,
            with clockwise orientation
        """

        return QgsGeometry.fromPolygon([[ self.midpoints[2], self.corners[3], self.corners[0], self.midpoints[0], self.midpoints[2] ]])

    def leftBox(self):
        """ Left hand side half of minimum oriented bounding box,
            with clockwise orientation
        """

        return QgsGeometry.fromPolygon([[ self.midpoints[2], self.midpoints[0], self.corners[1], self.corners[2], self.midpoints[2] ]])

    def axis_a(self):
        """ First axis of minimum oriented bounding box
            ie. segment [C, A]
        """

        return QgsGeometry.fromPolyline([ self.midpoints[2], self.midpoints[0] ])

    def axis_b(self):
        """ Second axis of minimum oriented bounding box
            ie. segment [B, D]
        """

        return QgsGeometry.fromPolyline([ self.midpoints[3], self.midpoints[1] ])

    def length(self):
        """ Length of first axis
        """

        return self.axis_a().length()

    def width(self):
        """ Length of second axis
        """

        return self.axis_b().length()

    def angle(self):
        """ Angle of first axis with respect to x axis in degrees
        """

        return segment_angle(self.midpoints[2], self.midpoints[0])

    def angle_b(self):
        """ Angle of second axis with respect to x axis in degrees
        """

        return segment_angle(self.midpoints[3], self.midpoints[1])

    def area(self):
        return self.minbox.area()


def mean_angle(segment):

    if segment.length() == 0.0:
        return 0.0

    dx = dy = 0.0

    if segment.isMultipart():

        for line in segment.asMultiPolyline():

            for a, b in zip(line[:-1], line[1:]):
                length = QgsGeometry.fromPolyline([ a, b ]).length()
                dx = dx + length * (b.x() - a.x())
                dy = dy + length * (b.y() - a.y())

    else:

        points = segment.asPolyline()

        for a, b in zip(points[:-1], points[1:]):
            length = QgsGeometry.fromPolyline([ a, b ]).length()
            dx = dx + length * (b.x() - a.x())
            dy = dy + length * (b.y() - a.y())

    dx = dx / segment.length()
    dy = dy / segment.length()

    return degrees(atan2(dy, dx))


class LeftRightBox(GeoAlgorithm):

    # Inputs

    DGO_POLYGONS = 'DGO_POLYGONS'
    # DGO_CENTROIDS = 'DGO_CENTROIDS'
    SPLIT_AXIS = 'SPLIT_AXIS'
    DGO_PRIMARY_KEY = 'DGO_PRIMARY_KEY'
    DGO_AXIS_FK = 'DGO_AXIS_FK'
    AXIS_PRIMARY_KEY = 'AXIS_PRIMARY_KEY'

    # Outputs

    OUTPUT = 'OUTPUT'
    OUTPUT_AXIS = 'OUTPUT_AXIS'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Left Right Box')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        # Inputs

        self.addParameter(ParameterVector(self.DGO_POLYGONS,
                                          self.tr('DGO Polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        # self.addParameter(ParameterVector(self.DGO_CENTROIDS,
        #                                   self.tr('DGO Centroids'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterTableField(self.DGO_PRIMARY_KEY,
                                              self.tr('DGO Primary Key'),
                                              parent=self.DGO_POLYGONS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.DGO_AXIS_FK,
                                              self.tr('DGO to Axis Foreign Key'),
                                              parent=self.DGO_POLYGONS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.SPLIT_AXIS,
                                          self.tr('Split Axis'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.AXIS_PRIMARY_KEY,
                                              self.tr('Split Axis Primary Key'),
                                              parent=self.SPLIT_AXIS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

         # Outputs

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Left Right Box')))

        self.addOutput(OutputVector(self.OUTPUT_AXIS, self.tr('Geometry Axes')))

    def processAlgorithm(self, progress):

        dgo_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.DGO_POLYGONS))
        # centroid_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.DGO_CENTROIDS))
        axis_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.SPLIT_AXIS))
        primary_key = self.getParameterValue(self.DGO_PRIMARY_KEY)
        axis_pk = self.getParameterValue(self.AXIS_PRIMARY_KEY)
        axis_fk = self.getParameterValue(self.DGO_AXIS_FK)

        # centroid_index = { f.attribute(primary_key) : f.id() for f in centroid_layer.getFeatures() }
        axis_index = { f.attribute(axis_pk) : f.id() for f in axis_layer.getFeatures() }

        dgos = vector.features(dgo_layer)
        total = 100.0 / len(dgos)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                dgo_layer,
                QgsField('SIDE', QVariant.Int, len=2),
                QgsField('LENGTH', QVariant.Double, len=10, prec=2),
                QgsField('WIDTH', QVariant.Double, len=10, prec=2),
                QgsField('BOXANGLE', QVariant.Double, len=10, prec=7),
                QgsField('AXANGLE', QVariant.Double, len=10, prec=7)
            ),
            QGis.WKBPolygon,
            dgo_layer.crs())

        axis_writer = self.getOutputFromName(self.OUTPUT_AXIS).getVectorWriter(
                [
                    vector_helper.resolveField(dgo_layer, primary_key),
                    QgsField('AXIS', QVariant.String, len=1),
                    QgsField('LENGTH', QVariant.Double, len=10, prec=2),
                    QgsField('ANGLE', QVariant.Double, len=10, prec=7),
                    QgsField('BOXAREA', QVariant.Double, len=10, prec=2),
                    QgsField('DGOAREA', QVariant.Double, len=10, prec=2)
                ],
                QGis.WKBLineString,
                dgo_layer.crs()
            )

        for current, dgo in enumerate(dgos):

            pk = dgo.attribute(primary_key)
            axis_id = dgo.attribute(axis_fk)
            dgo_area = dgo.area()

            if not axis_index.has_key(axis_id):
                continue
                
            splitter = axis_layer.getFeatures(QgsFeatureRequest(axis_index[axis_id])).next()
            intersection = dgo.geometry().intersection(splitter.geometry())

            try:

                if intersection.isMultipart():
                    origin = intersection.asMultiPolyline()[0][0]
                    outlet = intersection.asMultiPolyline()[-1][-1]
                else:
                    origin = intersection.asPolyline()[0]
                    outlet = intersection.asPolyline()[-1]

            except IndexError:

                continue

            axangle = mean_angle(intersection)
            leftRightBox = LeftRightBoxDescriptor(dgo.geometry(), origin, outlet, axangle)

            outfeature = QgsFeature()
            outfeature.setGeometry(leftRightBox.leftBox())
            outfeature.setAttributes(
                    dgo.attributes() + [
                        1,
                        leftRightBox.length(),
                        leftRightBox.width(),
                        leftRightBox.angle(),
                        axangle
                    ]
                )
            writer.addFeature(outfeature)

            outfeature = QgsFeature()
            outfeature.setGeometry(leftRightBox.rightBox())
            outfeature.setAttributes(
                    dgo.attributes() + [
                        -1,
                        leftRightBox.length(),
                        leftRightBox.width(),
                        leftRightBox.angle(),
                        axangle
                    ]
                )
            writer.addFeature(outfeature)

            outfeature = QgsFeature()
            outfeature.setGeometry(leftRightBox.axis_a())
            outfeature.setAttributes(
                    [
                        pk,
                        'A',
                        leftRightBox.length(),
                        leftRightBox.angle(),
                        leftRightBox.area(),
                        dgo_area
                    ]
                )
            axis_writer.addFeature(outfeature)

            outfeature = QgsFeature()
            outfeature.setGeometry(leftRightBox.axis_b())
            outfeature.setAttributes(
                    [
                        pk,
                        'B',
                        leftRightBox.width(),
                        leftRightBox.angle_b(),
                        leftRightBox.area(),
                        dgo_area
                    ]
                )
            axis_writer.addFeature(outfeature)
                    
            progress.setPercentage(int(current * total))



