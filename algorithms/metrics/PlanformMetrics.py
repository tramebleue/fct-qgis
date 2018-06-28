# -*- coding: utf-8 -*-

"""
***************************************************************************
    PlanformMetrics.py
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

from heapq import heappush, heappop, heapify
from functools import total_ordering

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

    @classmethod
    def merge(cls, bend1, bend2):

        assert(bend1.points[-1] == bend2.points[0])
        return cls(bend1.points[:-1] + bend2.points)

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

    def max_amplitude_stem(self):
        """

        Returns:
        - max amplitude stem as QgsGeometry (Line with 2 points)
        - index of max amplitude point
        """
        axis = QgsGeometry.fromPolyline([ self.p_origin, self.p_end ])
        max_amp = 0.0
        max_idx = 0
        stem = None

        for idx, p in enumerate(self.points):
            pt = QgsGeometry.fromPoint(p)
            amp = pt.distance(axis)
            if amp > max_amp:
                stem = axis.shortestLine(pt)
                max_amp = amp
                max_idx = idx

        return stem, max_idx

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

    def curvature_radius(self):
        return self.wavelength() * pow(self.sinuosity(), 1.5) / (13 * pow(self.sinuosity() - 1, 0.5))

def clamp_angle(angle):
    """ Return angle between -180 and +180 degrees
    """

    while angle <= -180:
        angle = angle + 360
    while angle > 180:
        angle = angle - 360
    return angle

@total_ordering
class QueueEntry(object):

    def __init__(self, index):

        self.index = index
        self.priority = float('inf')
        self.previous = None
        self.next = None
        self.interdistance = 0.0
        self.duplicate = False
        self.removed = False

    def __hash__(self):
        
        return self.key.__hash__()

    def __lt__(self, other):
        
        return self.priority < other.priority

    def __eq__(self, other):
        
        return self.priority == other.priority

    def __repr__(self):

        return 'QueueEntry %d previous = %s, next = %s, priority = %f, interdistance = %f' % (self.index, self.previous, self.next, self.priority, self.interdistance)

class PlanformMetrics(GeoAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    FLOW_AXIS = 'FLOW_AXIS'
    SEGMENTS = 'SEGMENTS'
    INFLECTION_POINTS = 'INFLECTION_POINTS'
    STEMS = 'STEMS'
    RESOLUTION = 'RESOLUTION'
    LMAX = 'LMAX'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Planform Metrics')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Center Line'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterNumber(self.RESOLUTION,
                                          self.tr('Amplitude Minimum Value'),
                                          minValue=0.0, default=5.0))

        self.addParameter(ParameterNumber(self.LMAX,
                                          self.tr('Maximum Interdistance'),
                                          minValue=0.0, default=200.0))

        self.addOutput(OutputVector(self.FLOW_AXIS, self.tr('Flow Axis')))
        self.addOutput(OutputVector(self.SEGMENTS, self.tr('Segments With Planform Metrics')))
        self.addOutput(OutputVector(self.INFLECTION_POINTS, self.tr('Inflection Points')))
        self.addOutput(OutputVector(self.STEMS, self.tr('Max Amplitude Stems')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        resolution = self.getParameterValue(self.RESOLUTION)
        lmax = self.getParameterValue(self.LMAX)

        axis_writer = self.getOutputFromName(self.FLOW_AXIS).getVectorWriter(
            layer.fields().toList() + [
                QgsField('BENDID', QVariant.Int, len=10)
                # QgsField('ANGLE', QVariant.Double, len=10, prec=6)
            ],
            QGis.WKBLineString,
            layer.crs())

        segment_writer = self.getOutputFromName(self.SEGMENTS).getVectorWriter(
            layer.fields().toList() + [
                QgsField('BENDID', QVariant.Int, len=10),
                QgsField('NPTS', QVariant.Int, len=4),
                QgsField('LBEND', QVariant.Double, len=10, prec=2),
                QgsField('LWAVE', QVariant.Double, len=10, prec=2),
                QgsField('SINUO', QVariant.Double, len=6, prec=4),
                QgsField('AMPLI', QVariant.Double, len=10, prec=4),
                QgsField('OMEG0', QVariant.Double, len=10, prec=8),
                QgsField('OMEG1', QVariant.Double, len=10, prec=6)
                # QgsField('RCURV', QVariant.Double, len=10, prec=3)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        inflection_points_writer = self.getOutputFromName(self.INFLECTION_POINTS).getVectorWriter(
            [
                QgsField('GID', QVariant.Int, len=10)
            ],
            QGis.WKBPoint,
            layer.crs())

        stem_writer = self.getOutputFromName(self.STEMS).getVectorWriter(
            [
                QgsField('BENDID', QVariant.Int, len=10),
                QgsField('AMPLI', QVariant.Double, len=10, prec=4)
            ],
            QGis.WKBLineString,
            layer.crs())

        def write_axis_segment(fid, p0, p1, feature):
            
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPolyline([p0, p1]))
            new_feature.setAttributes(feature.attributes() + [
                    fid
                    # clamp_angle(angle)
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
                    # bend.curvature_radius()
                ])
            segment_writer.addFeature(new_feature)

            stem, stem_idx = bend.max_amplitude_stem()

            if stem is None:
                ProcessingLog.addToLog(ProcessingLog.LOG_INFO, str(points))
                return

            stem_feature = QgsFeature()
            stem_feature.setGeometry(stem)
            stem_feature.setAttributes([
                    fid,
                    stem.length()
                ])
            stem_writer.addFeature(stem_feature)

        def write_inflection_point(point_id, point):

            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPoint(point))
            new_feature.setAttributes([
                    point_id
                ])
            inflection_points_writer.addFeature(new_feature)


        total = 100.0 / layer.featureCount()
        fid = 0
        point_id = 0
        # Total count of detected inflection points
        detected = 0
        # Total count of retained inflection points
        retained = 0

        for current, feature in enumerate(vector.features(layer)):

            points = feature.geometry().asPolyline()
            points_iterator = iter(points)
            a = next(points_iterator)
            b = next(points_iterator)
            current_sign = 0
            current_segment = [ a ]
            current_axis_direction = None

            bends = list()
            inflection_points = list()

            # write_inflection_point(point_id, a)
            point_id = point_id + 1

            for c in points_iterator:

                sign = angle_sign(a, b, c)
                
                if current_sign * sign < 0:

                    p0 = current_segment[0]
                    pi = QgsPoint(0.5 * (a.x() + b.x()), 0.5 * (a.y() + b.y()))
                    current_segment.append(pi)
                    
                    if current_axis_direction:
                        angle = current_axis_direction.angle(qgs_vector(p0, pi)) * 180 / PI
                    else:
                        angle = 0.0
                    
                    # write_axis_segment(fid, p0, pi, feature, angle)
                    # write_segment(fid, current_segment, feature)
                    # write_inflection_point(point_id, pi)

                    bend = Bend(current_segment)
                    bends.append(bend)
                    inflection_points.append(p0)
                    
                    current_sign = sign
                    current_segment = [ pi, b ]
                    current_axis_direction = qgs_vector(p0, pi)
                    fid = fid + 1
                    point_id = point_id + 1

                else:

                    current_segment.append(b)

                if current_sign == 0:
                    current_sign = sign

                a, b = b, c

            p0 = current_segment[0]

            if current_axis_direction:
                angle = current_axis_direction.angle(qgs_vector(p0, b)) * 180 / PI
            else:
                angle = 0.0

            # write_axis_segment(fid, p0, b, feature, angle)
            current_segment.append(b)
            
            # write_segment(fid, current_segment, feature)
            # write_inflection_point(point_id, b)
            bend = Bend(current_segment)
            bends.append(bend)
            inflection_points.append(p0)
            inflection_points.append(b)

            fid = fid + 1
            point_id = point_id + 1

            detected = detected + len(inflection_points)

            # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Inflections points = %d' % len(inflection_points))
            # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Bends = %d' % len(bends))

            # Filter out smaller bends

            entries = list()

            entry = QueueEntry(0)
            entry.previous = None
            entry.next = 1
            entry.priority = float('inf')
            entry.interdistance = float('inf')
            entries.append(entry)

            for k in range(1, len(inflection_points)-1):
                
                entry = QueueEntry(k)
                entry.previous = k-1
                entry.next = k+1
                entry.priority = bends[k-1].amplitude() + bends[k].amplitude()
                entry.interdistance = qgs_vector(inflection_points[k-1], inflection_points[k]).length() + \
                                      qgs_vector(inflection_points[k], inflection_points[k+1]).length()
                entries.append(entry)

            k = len(inflection_points) - 1
            entry = QueueEntry(k)
            entry.previous = k-1
            entry.next = None
            entry.priority = float('inf')
            entry.interdistance = float('inf')
            entries.append(entry)

            queue = list(entries)
            heapify(queue)

            while queue:

                entry = heappop(queue)
                k = entry.index

                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Entry = %s' % entry)

                if entry.priority > 2*resolution:
                    break

                if entry.duplicate or entry.removed:
                    continue

                if entry.interdistance > lmax:
                    continue

                previous_entry = entries[entry.previous]
                next_entry = entries[entry.next]

                if previous_entry.previous is None:
                    continue

                if next_entry.next is None:
                    continue

                new_entry = QueueEntry(k)
                
                entries[previous_entry.previous].next = k
                new_entry.previous = previous_entry.previous
                
                entries[next_entry.next].previous = k
                new_entry.next = next_entry.next

                before_bend = Bend.merge(bends[new_entry.previous], bends[entry.previous])
                after_bend = Bend.merge(bends[k], bends[entry.next])

                bends[new_entry.previous] = before_bend
                bends[k] = after_bend

                new_entry.priority = before_bend.amplitude() + after_bend.amplitude()
                new_entry.interdistance = qgs_vector(inflection_points[new_entry.previous], inflection_points[k]).length() + \
                                      qgs_vector(inflection_points[k], inflection_points[new_entry.next]).length()

                heappush(queue, new_entry)

                entries[k] = new_entry
                previous_entry.removed = True
                next_entry.removed = True
                entry.duplicate = True

            # Output results

            index = 0

            while True:

                entry = entries[index]
                point = inflection_points[index]

                if entry.next is None:

                    point_id = point_id + 1
                    write_inflection_point(point_id, point)
                    retained = retained + 1
                    break
                
                bend = bends[index]
                point_id = point_id + 1
                fid = fid + 1

                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Points = %s' % bend.points)
                write_inflection_point(point_id, point)
                retained = retained + 1
                write_axis_segment(fid, bend.p_origin, bend.p_end, feature)
                write_segment(fid, bend.points, feature)

                index = entry.next

            progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Retained inflection points = %d / %d' % (retained, detected))