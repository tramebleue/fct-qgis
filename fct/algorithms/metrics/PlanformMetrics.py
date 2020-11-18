# -*- coding: utf-8 -*-

"""
Planform Metrics

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
from heapq import heappush, heappop, heapify
from functools import total_ordering

import numpy as np

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsVector,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

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

    a, b, c: QgsPointXY
    returns QgsPointXY
    """

    xab = b.x() - a.x()
    yab = b.y() - a.y()

    A = np.array([[ -yab, xab ],[ xab, yab ]])
    B = np.array([ a.x()*yab + a.y()*xab, c.x()*xab + c.y()*yab ])
    x, y = np.linalg.inv(A).dot(B)

    return QgsPointXY(x, y)

def distance_to_line(a, b, c):
    """ Euclidean distance from point C to line (A, B)

    a, b, c: QgsPointXY
    returns distance (float)
    """

    p = project_point(a, b, c)
    return math.sqrt((c.x() - p.x())**2 + (c.y() - p.y())**2)

def qgs_vector(p0, p1):
    return QgsVector(p1.x() - p0.x(), p1.y() - p0.y())

class Bend(object):

    def __init__(self, points, measure):
        self.points = points
        self.measure = measure

    @classmethod
    def merge(cls, bend1, bend2):

        assert(bend1.points[-1] == bend2.points[0])
        return cls(bend1.points[:-1] + bend2.points, bend2.measure)

    @property
    def p_origin(self):
        return self.points[0]

    @property
    def p_end(self):
        return self.points[-1]

    def npoints(self):
        return len(self.points)

    def amplitude(self):
        axis = QgsGeometry.fromPolylineXY([ self.p_origin, self.p_end ])
        amp = max([ QgsGeometry.fromPointXY(p).distance(axis) for p in self.points ])
        # amp = max([ distance_to_line(self.p_origin, self.p_end, p) for p in self.points ])
        return amp

    def max_amplitude_stem(self):
        """

        Returns:
        - max amplitude stem as QgsGeometry (Line with 2 points)
        - index of max amplitude point
        """
        axis = QgsGeometry.fromPolylineXY([ self.p_origin, self.p_end ])
        max_amp = 0.0
        max_idx = 0
        stem = None

        for idx, p in enumerate(self.points):
            pt = QgsGeometry.fromPointXY(p)
            amp = pt.distance(axis)
            if amp > max_amp:
                stem = axis.shortestLine(pt)
                max_amp = amp
                max_idx = idx

        return stem, max_idx

    def wavelength(self):
        axis = QgsGeometry.fromPolylineXY([ self.p_origin, self.p_end ])
        return 2 * axis.length()

    def length(self):
        return QgsGeometry.fromPolylineXY(self.points).length()

    def sinuosity(self):
        return 2 * self.length() / self.wavelength()

    def omega_origin(self):
        axis_direction = qgs_vector(self.p_origin, self.p_end)
        p0 = self.points[0]
        p1 = self.points[1]
        return axis_direction.angle(qgs_vector(p0, p1)) * 180 / math.pi

    def omega_end(self):
        axis_direction = qgs_vector(self.p_origin, self.p_end)
        p0 = self.points[-2]
        p1 = self.points[-1]
        return axis_direction.angle(qgs_vector(p0, p1)) * 180 / math.pi

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

    def __lt__(self, other):
        
        return self.priority < other.priority

    def __eq__(self, other):
        
        return self.priority == other.priority

    def __repr__(self):

        return 'QueueEntry %d previous = %s, next = %s, priority = %f, interdistance = %f' % (self.index, self.previous, self.next, self.priority, self.interdistance)

class PlanformMetrics(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Disaggregate stream polyline by inflection points,
    and compute planform metrics.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'PlanformMetrics')

    # Input Parameters

    INPUT = 'INPUT'
    RESOLUTION = 'RESOLUTION'
    LMAX = 'LMAX'
    MAX_ANGLE = 'MAX_ANGLE'

    # Output Parameters

    OUTPUT = 'OUTPUT'
    FLOW_AXIS = 'FLOW_AXIS'
    INFLECTION_POINTS = 'INFLECTION_POINTS'
    STEMS = 'STEMS'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        # Input Parameters

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream Polyline'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterDistance(
            self.RESOLUTION,
            self.tr('Amplitude Minimum Value'),
            parentParameterName=self.INPUT,
            defaultValue=10.0))

        self.addParameter(QgsProcessingParameterDistance(
            self.LMAX,
            self.tr('Maximum Interdistance'),
            parentParameterName=self.INPUT,
            defaultValue=200.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.MAX_ANGLE,
            self.tr('Maximum Axis Angle (Degrees)'),
            defaultValue=50.0))

        # Output Parameters

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Segments Between Inflection Points'),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.FLOW_AXIS,
            self.tr('Inflection Line'),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.INFLECTION_POINTS,
            self.tr('Inflection Points'),
            QgsProcessing.TypeVectorPoint))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.STEMS,
            self.tr('Max Amplitude'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        resolution = self.parameterAsDouble(parameters, self.RESOLUTION, context)
        lmax = self.parameterAsDouble(parameters, self.LMAX, context)
        # max_angle = self.parameterAsDouble(parameters, self.MAX_ANGLE, context)

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Multipart geometries are not currently supported'), True)
            return {}

        (axis_sink, axis_id) = self.parameterAsSink(
            parameters, self.FLOW_AXIS, context,
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs())

        fields = QgsFields(layer.fields())
        fields.append(QgsField('BENDID', QVariant.Int, len=10))
        fields.append(QgsField('BENDM', QVariant.Double, len=10, prec=2))
        fields.append(QgsField('NPTS', QVariant.Int, len=4))
        fields.append(QgsField('LBEND', QVariant.Double, len=10, prec=2))
        fields.append(QgsField('LWAVE', QVariant.Double, len=10, prec=2))
        fields.append(QgsField('SINUO', QVariant.Double, len=6, prec=4))
        fields.append(QgsField('AMPLI', QVariant.Double, len=10, prec=4))
        fields.append(QgsField('OMEG0', QVariant.Double, len=10, prec=8))
        fields.append(QgsField('OMEG1', QVariant.Double, len=10, prec=6))
        # QgsField('RCURV', QVariant.Double, len=10, prec=3)

        (segment_sink, segment_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        fields = QgsFields()
        fields.append(QgsField('GID', QVariant.Int, len=10))
        fields.append(QgsField('ANGLE', QVariant.Double, len=10, prec=6))
        fields.append(QgsField('INTERDIST', QVariant.Double, len=10, prec=6))

        (inflection_sink, inflection_id) = self.parameterAsSink(
            parameters, self.INFLECTION_POINTS, context,
            fields,
            QgsWkbTypes.Point,
            layer.sourceCrs())

        fields = QgsFields()
        fields.append(QgsField('BENDID', QVariant.Int, len=10))
        fields.append(QgsField('AMPLI', QVariant.Double, len=10, prec=4))

        (stem_sink, stem_id) = self.parameterAsSink(
            parameters, self.STEMS, context,
            fields,
            QgsWkbTypes.LineString,
            layer.sourceCrs())

        def write_axis_segment(fid, p0, p1, feature):
            
            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPolylineXY([p0, p1]))
            new_feature.setAttributes(feature.attributes() + [
                    fid
                    # clamp_angle(angle)
                ])
            axis_sink.addFeature(new_feature)

        def write_segment(fid, bend, feature):

            # bend = Bend(points, measure)

            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPolylineXY(bend.points))
            new_feature.setAttributes(feature.attributes() + [
                    fid,
                    bend.measure,
                    bend.npoints(),
                    bend.length(),
                    bend.wavelength(),
                    bend.sinuosity(),
                    bend.amplitude(),
                    bend.omega_origin(),
                    bend.omega_end()
                    # bend.curvature_radius()
                ])
            segment_sink.addFeature(new_feature)

            stem, stem_idx = bend.max_amplitude_stem()

            if stem is None:
                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, str(points))
                return

            stem_feature = QgsFeature()
            stem_feature.setGeometry(stem)
            stem_feature.setAttributes([
                    fid,
                    stem.length()
                ])
            stem_sink.addFeature(stem_feature)

        def write_inflection_point(point_id, point, angle, interdistance):

            new_feature = QgsFeature()
            new_feature.setGeometry(QgsGeometry.fromPointXY(point))
            new_feature.setAttributes([
                    point_id,
                    angle,
                    interdistance
                ])
            inflection_sink.addFeature(new_feature)

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        fid = 0
        point_id = 0
        # Total count of detected inflection points
        detected = 0
        # Total count of retained inflection points
        retained = 0

        for current, feature in enumerate(layer.getFeatures()):

            points = feature.geometry().asPolyline()
            points_iterator = iter(points)
            a = next(points_iterator)
            b = next(points_iterator)
            current_sign = 0
            current_segment = [a]
            current_axis_direction = None

            bends = list()
            inflection_points = list()

            def axis_angle(entry):

                if entry.previous is None or entry.next is None:
                    return 0.0

                a = inflection_points[entry.previous]
                b = inflection_points[entry.index]
                c = inflection_points[entry.next]
                ab = qgs_vector(a, b)
                bc = qgs_vector(b, c)

                return clamp_angle(math.degrees(ab.angle(bc)))

            def interdistance(entry):

                l1 = entry.previous and qgs_vector(inflection_points[entry.previous], inflection_points[entry.index]).length() or 0.0
                l2 = entry.next and qgs_vector(inflection_points[entry.index], inflection_points[entry.next]).length() or 0.0

                return l1 + l2

            # write_inflection_point(point_id, a)
            point_id = point_id + 1
            measure = 0.0

            for c in points_iterator:

                sign = angle_sign(a, b, c)

                if current_sign * sign < 0:

                    p0 = current_segment[0]
                    pi = QgsPointXY(0.5 * (a.x() + b.x()), 0.5 * (a.y() + b.y()))
                    current_segment.append(pi)
                    measure += qgs_vector(p0, pi).length()

                    if current_axis_direction:
                        angle = current_axis_direction.angle(qgs_vector(p0, pi)) * 180 / math.pi
                    else:
                        angle = 0.0

                    # write_axis_segment(fid, p0, pi, feature, angle)
                    # write_segment(fid, current_segment, feature)
                    # write_inflection_point(point_id, pi)

                    bend = Bend(current_segment, measure)
                    bends.append(bend)
                    inflection_points.append(p0)

                    current_sign = sign
                    current_segment = [pi, b]
                    measure += qgs_vector(pi, b).length()
                    current_axis_direction = qgs_vector(p0, pi)
                    fid = fid + 1
                    point_id = point_id + 1

                else:

                    current_segment.append(b)
                    measure += qgs_vector(a, b).length()

                if current_sign == 0:
                    current_sign = sign

                a, b = b, c

            p0 = current_segment[0]

            if current_axis_direction:
                angle = current_axis_direction.angle(qgs_vector(p0, b)) * 180 / math.pi
            else:
                angle = 0.0

            # write_axis_segment(fid, p0, b, feature, angle)
            current_segment.append(b)
            measure += qgs_vector(a, b).length()

            # write_segment(fid, current_segment, feature)
            # write_inflection_point(point_id, b)
            bend = Bend(current_segment, measure)
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

            # Filter out large axis angles

            # if max_angle > 0.0:

            #     index = 0
            #     queue = list()

            #     while True:

            #         entry = entries[index]

            #         if entry.previous is None or entry.next is None:

            #             entry.priority = 0.0
            #             queue.append(entry)

            #             if entry.next is None:
            #                 break
            #             else:
            #                 index = entry.next
            #                 continue

            #         # -priority to sort entries from large to small angle
            #         entry.priority = -abs(axis_angle(entry))
            #         queue.append(entry)

            #         index = entry.next

            #     heapify(queue)

            #     while queue:

            #         entry = heappop(queue)
            #         angle = -entry.priority

            #         if angle < max_angle:
            #             break

            #         if entry.duplicate or entry.removed:
            #             continue

            #         if entry.previous is None or entry.next is None:
            #             continue

            #         if entry.interdistance > 2*lmax:
            #             continue

            #         previous_entry = entries[entry.previous]
            #         next_entry = entries[entry.next]

            #         merged_bend = Bend.merge(bends[entry.previous], bends[entry.index])
            #         bends[entry.previous] = merged_bend

            #         previous_entry.duplicate = True
            #         new_previous_entry = QueueEntry(previous_entry.index)
            #         new_previous_entry.previous = previous_entry.previous
            #         new_previous_entry.next = entry.next
            #         angle = axis_angle(new_previous_entry)
            #         dist = new_previous_entry.interdistance = interdistance(new_previous_entry)
            #         new_previous_entry.priority = -abs(angle)
            #         entries[new_previous_entry.index] = new_previous_entry
            #         heappush(queue, new_previous_entry)

            #         next_entry.duplicate = True
            #         new_next_entry = QueueEntry(next_entry.index)
            #         new_next_entry.previous = entry.previous
            #         new_next_entry.next = next_entry.next
            #         angle = axis_angle(new_next_entry)
            #         dist = new_next_entry.interdistance = interdistance(new_next_entry)
            #         new_next_entry.priority = -abs(angle)
            #         entries[new_next_entry.index] = new_next_entry
            #         heappush(queue, new_next_entry)

            #         entry.removed = True

            # Output results

            index = 0

            while True:

                entry = entries[index]
                point = inflection_points[index]

                if entry.next is None:

                    point_id = point_id + 1
                    angle = axis_angle(entry)
                    dist = interdistance(entry)
                    write_inflection_point(point_id, point, angle, dist)
                    retained = retained + 1
                    break

                bend = bends[index]
                point_id = point_id + 1
                fid = fid + 1

                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Points = %s' % bend.points)
                angle = axis_angle(entry)
                dist = interdistance(entry)
                write_inflection_point(point_id, point, angle, dist)
                retained = retained + 1
                write_axis_segment(fid, bend.p_origin, bend.p_end, feature)
                write_segment(fid, bend, feature)

                index = entry.next

            feedback.setProgress(int(current * total))

        feedback.pushInfo('Retained inflection points = %d / %d' % (retained, detected))

        return {
            self.OUTPUT: segment_id,
            self.FLOW_AXIS: axis_id,
            self.INFLECTION_POINTS: inflection_id,
            self.STEMS: stem_id
        }
