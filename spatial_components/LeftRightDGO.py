# -*- coding: utf-8 -*-

"""
***************************************************************************
    LeftRightDGO.py
    ---------------------
    Date                 : April 2018
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
from ..core import vector as vector_helper
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

def side_of_linestring(o, linestring):
    """
    Parameters
    ----------

    o: QgsPoint
    linestring: QgsGeometry, Line

    Returns
    -------

    -1 if `o` is right to `linestring',
     1 if `o` is left to `linestring',
     0 if `o` is neither right or left to `linestring',
       ie. `o` lies exactly on `linestring` 
    """

    if linestring.length() == 0.0:
        return 0

    ptgeom = QgsGeometry.fromPoint(o)
    min_distance = float('inf')
    side = 0

    if linestring.isMultipart():

        for points in linestring.asMultiPolyline():

            for a, b in zip(points[:-1], points[1:]):

                distance = QgsGeometry.fromPolyline([ a, b ]).distance(ptgeom)
                if distance < min_distance:
                    side = side_of_line(o, a, b)
                    min_distance = distance

    else:

        points = linestring.asPolyline()

        for a, b in zip(points[:-1], points[1:]):

            distance = QgsGeometry.fromPolyline([ a, b ]).distance(ptgeom)
            if distance < min_distance:
                side = side_of_line(o, a, b)
                min_distance = distance

    return side

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

def farthest_point(transect, origin):

    if transect.type() != QGis.Line:
        return None, 0.0

    if transect.isMultipart():

        # When the transect is multipart,
        # we assume the original DGO shape is complicated,
        # and, as a consequence, we consider that
        # only the first part of the transect is relevant

        points = transect.asMultiPolyline()[0]

        if len(points) > 1:
            pole = points[-1]
            return pole, origin.distance(QgsGeometry.fromPoint(pole))

    else:

        points = transect.asPolyline()
        if len(points) > 1:
            pole = points[-1]
            return pole, origin.distance(QgsGeometry.fromPoint(pole))

    return None, 0.0


def maximum_width(geom, origin):
    """
    Parameters
    ----------

    geom: QgsGeometry, Polygon
    origin: QgsGeometry, Point

    Returns
    -------

    pole: QgsPoint
        Farthest point in geom exterior boundary,
        with respect to origin

    max_width: float
        Maximum distance
        from origin to geom exterior boundary
    """

    # max_width = 0
    # other_pole = origin
    # exterior = geom.asPolygon()[0]

    # for pt in exterior:

    #     d = origin.distance(QgsGeometry.fromPoint(pt))
    #     if d > max_width:
    #         max_width = d
    #         other_pole = pt

    # return other_pole, max_width

    minbox = minimum_oriented_boundingbox(geom)
    exterior = minbox.asPolygon()[0]

    closest_point = minbox.nearestPoint(origin).asPoint()

    distance, segment, vertex = minbox.closestSegmentWithContext(origin.asPoint())
    v0 = (vertex + 1) % (len(exterior) - 1)
    v1 = (vertex + 2) % (len(exterior) - 1)

    opposite_segment =  QgsGeometry.fromPolyline([ exterior[v0], exterior[v1] ])
    opposite_point = opposite_segment.nearestPoint(origin).asPoint()

    transect = QgsGeometry.fromPolyline([ closest_point, opposite_point ]).intersection(geom)
    pole, distance = farthest_point(transect, origin)

    if pole is None:

        v0 = (v0 + 2) % (len(exterior) - 1)
        v1 = (v1 + 2) % (len(exterior) - 1)

        opposite_segment =  QgsGeometry.fromPolyline([ exterior[v0], exterior[v1] ])
        opposite_point = opposite_segment.nearestPoint(origin).asPoint()

        transect = QgsGeometry.fromPolyline([ closest_point, opposite_point ]).intersection(geom)
        pole, distance = farthest_point(transect, origin)

        if pole is None:

            return opposite_point, origin.distance(QgsGeometry.fromPoint(opposite_point))

        else:

            return pole, distance

    else:

        return pole, distance


class LeftRightDGO(GeoAlgorithm):

    # Inputs

    DGO_POLYGONS = 'DGO_POLYGONS'
    DGO_CENTROIDS = 'DGO_CENTROIDS'
    SPLIT_AXIS = 'SPLIT_AXIS'
    DGO_PRIMARY_KEY = 'DGO_PRIMARY_KEY'
    DGO_AXIS_FK = 'DGO_AXIS_FK'
    AXIS_PRIMARY_KEY = 'AXIS_PRIMARY_KEY'

    # Outputs

    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Left Right DGO')
        self.group, self.i18n_group = self.trAlgorithm('Spatial Components')

        # Inputs

        self.addParameter(ParameterVector(self.DGO_POLYGONS,
                                          self.tr('DGO Polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterVector(self.DGO_CENTROIDS,
                                          self.tr('DGO Centroids'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterTableField(self.DGO_PRIMARY_KEY,
                                              self.tr('DGO Primary Key'),
                                              parent=self.DGO_CENTROIDS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.DGO_AXIS_FK,
                                              self.tr('DGO to Axis Foreign Key'),
                                              parent=self.DGO_CENTROIDS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.SPLIT_AXIS,
                                          self.tr('Split Axis'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.AXIS_PRIMARY_KEY,
                                              self.tr('Split Axis Primary Key'),
                                              parent=self.SPLIT_AXIS,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

         # Outputs

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Left Right DGO')))

    def processAlgorithm(self, progress):

        dgo_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.DGO_POLYGONS))
        centroid_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.DGO_CENTROIDS))
        axis_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.SPLIT_AXIS))
        primary_key = self.getParameterValue(self.DGO_PRIMARY_KEY)
        axis_pk = self.getParameterValue(self.AXIS_PRIMARY_KEY)
        axis_fk = self.getParameterValue(self.DGO_AXIS_FK)

        centroid_index = { f.attribute(primary_key) : f.id() for f in centroid_layer.getFeatures() }
        axis_index = { f.attribute(axis_pk) : f.id() for f in axis_layer.getFeatures() }

        dgos = vector.features(dgo_layer)
        total = 100.0 / len(dgos)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                dgo_layer,
                QgsField('SIDE', QVariant.Int, len=2),
                QgsField('HALFWIDTH', QVariant.Double, len=10, prec=2)
            ),
            dgo_layer.dataProvider().geometryType(),
            dgo_layer.crs())

        for current, dgo in enumerate(dgos):

            pk = dgo.attribute(primary_key)

            if not centroid_index.has_key(pk):
                continue

            centroid = centroid_layer.getFeatures(QgsFeatureRequest(centroid_index[pk])).next()
            axis_id = centroid.attribute(axis_fk)

            if not axis_index.has_key(axis_id):
                continue
                
            origin = centroid.geometry()
            splitter = axis_layer.getFeatures(QgsFeatureRequest(axis_index[axis_id])).next()
            intersection = dgo.geometry().intersection(splitter.geometry())

            try:

                if intersection.isMultipart():
                    outlet = intersection.asMultiPolyline()[-1][-1]
                else:
                    outlet = intersection.asPolyline()[-1]

            except IndexError:

                outfeature = QgsFeature()
                outfeature.setGeometry(dgo.geometry())
                outfeature.setAttributes(
                    dgo.attributes() + [
                        0,
                        0.0
                    ]
                )
                writer.addFeature(outfeature)

                continue

            dgo_geom = QgsGeometry(dgo.geometry())
            splitted, sides, test_points = dgo_geom.splitGeometry(splitter.geometry().asPolyline(), True)

            if splitted == 0:

                # QgsGeometry().splitGeometry() returns one part as the modified input geometry,
                # though this is not very intuitive
                sides.append(dgo_geom)

                for geom in sides:

                    pole, max_width = maximum_width(geom, origin)
                    side = side_of_linestring(geom.pointOnSurface().asPoint(), intersection)

                    outfeature = QgsFeature()
                    outfeature.setGeometry(geom)
                    outfeature.setAttributes(
                        dgo.attributes() + [
                            side,
                            max_width
                        ]
                    )
                    writer.addFeature(outfeature)

            else:

                outfeature = QgsFeature()
                outfeature.setGeometry(dgo.geometry())
                outfeature.setAttributes(
                    dgo.attributes() + [
                        0,
                        0.0
                    ]
                )
                writer.addFeature(outfeature)
                    

            progress.setPercentage(int(current * total))



