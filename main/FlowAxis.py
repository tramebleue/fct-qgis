# -*- coding: utf-8 -*-

"""
***************************************************************************
    NodesFromEdges.py
    ---------------------
    Date                 : February 2018
    Copyright            : (C) 2016 by Christophe Rousson
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
from math import sqrt
from math import pi as PI
import numpy as np

def angle_sign(a, b, c):

    xab = b.x() - a.x()
    yab = b.y() - a.y()
    xac = c.x() - a.x()
    yac = c.y() - a.y()
    dot = (xab * yac) - (yab * xac)

    if dot == 0:
        return 0
    elif dot > 0:
        return 1
    else:
        return -1

def project_point(a, b, c):
    """ Project point C on line (A, B)

    a, b, c: QgsPoint
    returns QgsPoint
    """

    xab = b.x() - a.x()
    yab = b.y() - a.y()

    A = np.array([[ -yab, xab ],[ xab, yab ]])
    B = np.array([ a.x()*yab + a.y()*xab, c.x()*xab + c.y()*yab ])
    x, y = np.linalg.inv(A).dot(B)

    return QgsPoint(x, y)

def distance_to_line(a, b, c):
    """ Euclidean distance from point C to line (A, B)

    a, b, c: QgsPoint
    returns distance (float)
    """

    p = project_point(a, b, c)
    return sqrt((c.x() - p.x())**2 + (c.y() - p.y())**2)

def qgs_vector(p0, p1):
    return QgsVector(p1.x() - p0.x(), p1.y() - p0.y())

class Bend(object):

    def __init__(self, points):
        self.points = points

    @property
    def p_origin(self):
        return self.points[0]

    @property
    def p_end(self):
        return self.points[-1]

    def npoints(self):
        return len(self.points)

    def amplitude(self):
        axis = QgsGeometry.fromPolyline([ self.p_origin, self.p_end ])
        amp = max([ QgsGeometry.fromPoint(p).distance(axis) for p in self.points ])
        # amp = max([ distance_to_line(self.p_origin, self.p_end, p) for p in self.points ])
        return amp

    def wavelength(self):
        axis = QgsGeometry.fromPolyline([ self.p_origin, self.p_end ])
        return 2 * axis.length()

    def length(self):
        return QgsGeometry.fromPolyline(self.points).length()

    def sinuosity(self):
        return 2 * self.length() / self.wavelength()

    def omega_origin(self):
        axis_direction = qgs_vector(self.p_origin, self.p_end)
        p0 = self.points[0]
        p1 = self.points[1]
        return axis_direction.angle(qgs_vector(p0, p1)) * 180 / PI

    def omega_end(self):
        axis_direction = qgs_vector(self.p_origin, self.p_end)
        p0 = self.points[-2]
        p1 = self.points[-1]
        return axis_direction.angle(qgs_vector(p0, p1)) * 180 / PI

def clamp_angle(angle):
    """ Return angle between -180 and +180 degrees
    """

    while angle <= -180:
        angle = angle + 360
    while angle > 180:
        angle = angle - 360
    return angle



class FlowAxis(GeoAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    FLOW_AXIS = 'FLOW_AXIS'
    SEGMENTS = 'SEGMENTS'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Flow Axis (Inflection Points)')
        self.group, self.i18n_group = self.trAlgorithm('Spatial Components')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Directed Polylines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputVector(self.FLOW_AXIS, self.tr('Flow Axis')))
        self.addOutput(OutputVector(self.SEGMENTS, self.tr('Segments')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))

        axis_writer = self.getOutputFromName(self.FLOW_AXIS).getVectorWriter(
            layer.fields().toList() + [
                QgsField('AXISID', QVariant.Int, len=10),
                QgsField('ANGLE', QVariant.Double, len=10, prec=6)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        segment_writer = self.getOutputFromName(self.SEGMENTS).getVectorWriter(
            layer.fields().toList() + [
                QgsField('AXISID', QVariant.Int, len=10),
                QgsField('NPTS', QVariant.Int, len=4),
                QgsField('LBEND', QVariant.Double, len=10, prec=2),
                QgsField('LWAVE', QVariant.Double, len=10, prec=2),
                QgsField('SINUO', QVariant.Double, len=6, prec=4),
                QgsField('AMPLI', QVariant.Double, len=10, prec=4),
                QgsField('OMEG0', QVariant.Double, len=10, prec=8),
                QgsField('OMEG1', QVariant.Double, len=10, prec=6)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        def write_axis_segment(fid, p0, p1, feature, angle):
            
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPolyline([p0, p1]))
            new_feature.setAttributes(feature.attributes() + [
                    fid,
                    clamp_angle(angle)
                ])
            axis_writer.addFeature(new_feature)

        def write_segment(fid, points, feature):
            
            bend = Bend(points)
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPolyline(points))
            new_feature.setAttributes(feature.attributes() + [
                    fid,
                    bend.npoints(),
                    bend.length(),
                    bend.wavelength(),
                    bend.sinuosity(),
                    bend.amplitude(),
                    bend.omega_origin(),
                    bend.omega_end()
                ])
            segment_writer.addFeature(new_feature)

        total = 100.0 / layer.featureCount()
        fid = 0

        for current, feature in enumerate(vector.features(layer)):

            points = feature.geometry().asPolyline()
            points_iterator = iter(points)
            a = next(points_iterator)
            b = next(points_iterator)
            current_sign = 0
            current_segment = [ a, b ]
            current_axis_direction = None

            for c in points_iterator:

                sign = angle_sign(a, b, c)
                
                if current_sign * sign < 0:

                    pi = QgsPoint(0.5 * (a.x() + b.x()), 0.5 * (a.y() + b.y()))
                    current_segment.pop()
                    current_segment.append(pi)
                    p0 = current_segment[0]
                    
                    if current_axis_direction:
                        angle = current_axis_direction.angle(qgs_vector(p0, pi)) * 180 / PI
                    else:
                        angle = 0.0
                    
                    write_axis_segment(fid, p0, pi, feature, angle)
                    write_segment(fid, current_segment, feature)
                    
                    current_sign = sign
                    current_segment = [ pi, b ]
                    current_axis_direction = qgs_vector(p0, pi)
                    fid = fid + 1

                if current_sign == 0:
                    current_sign = sign

                current_segment.append(c)
                a, b = b, c

            p0 = current_segment[0]
            if current_axis_direction:
                angle = current_axis_direction.angle(qgs_vector(p0, b)) * 180 / PI
            else:
                angle = 0.0

            write_axis_segment(fid, p0, b, feature, angle)
            write_segment(fid, current_segment, feature)
            fid = fid + 1

            progress.setPercentage(int(current * total))