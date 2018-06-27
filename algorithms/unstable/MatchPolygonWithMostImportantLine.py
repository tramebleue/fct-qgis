# -*- coding: utf-8 -*-

"""
***************************************************************************
    MatchPolygonWithMostImportantLine.py
    ---------------------
    Date                 : February 2018
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

def lineLocatePoint(line, point):
    """
    Returns a distance representing the location along this linestring of the closest point
    on this linestring geometry to the specified point.
    ie, the returned value indicates how far along this linestring you need to traverse
    to get to the closest location where this linestring comes to the specified point.

    Note: This function exists in QGis from version 3.0

    Parameters
    ----------

    line: QgsGeometry, LineString

    point: QgsGeometry, Point
        point to seek proximity to

    Returns
    -------

    distance along line, or -1 if error
    """

    if line.isMultipart(): return -1

    measure = 0.0
    closest = float('inf')
    closest_measure = 0.0
    closest_segment = None
    closest_vertex = None
    vertices = line.asPolyline()

    for v0, v1 in zip(vertices[:-1], vertices[1:]):

        segment = QgsGeometry.fromPolyline([ v0, v1 ])
        d = segment.distance(point)

        if d < closest:
            closest = d
            closest_segment = segment
            closest_measure = measure
            closest_vertex = v0

        measure = measure + segment.length()

    projected_point = closest_segment.nearestPoint(point)
    closest_measure = closest_measure + QgsGeometry.fromPoint(closest_vertex).distance(projected_point)

    return closest_measure

class MatchPolygonWithMostImportantLine(GeoAlgorithm):

    INPUT = 'INPUT'
    INPUT_CENTROIDS = 'INPUT_CENTROIDS'
    INPUT_PK = 'INPUT_PK'
    INPUT_LINES = 'INPUT_LINES'
    LINE_PK = 'LINE_PK'
    ORDER_FIELD = 'ORDER_FIELD'
    ASCENDING_ORDER = 'ASCENDING_ORDER'
    MEASURE_FIELD = 'MEASURE_FIELD'
    OUTPUT = 'OUTPUT'
    OUTPUT_CENTROID = 'OUTPUT_CENTROID'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Match Polygon With Most Important Line')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterVector(self.INPUT_CENTROIDS,
                                          self.tr('Input Polygon Centroids'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterTableField(self.INPUT_PK,
                                              self.tr('Polygon Primary Key'),
                                              parent=self.INPUT,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.INPUT_LINES,
                                          self.tr('Measured Lines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.LINE_PK,
                                              self.tr('Line Primary Key'),
                                              parent=self.INPUT_LINES,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.ORDER_FIELD,
                                              self.tr('Line Order Field'),
                                              parent=self.INPUT_LINES,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterBoolean(self.ASCENDING_ORDER,
                                           self.tr('Ascending Order'),
                                           default=False))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                          self.tr('Line Measure Field'),
                                          parent=self.INPUT_LINES,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        # self.addParameter(ParameterNumber(self.MAX_DISTANCE,
        #                                   self.tr('Maximum Distance'),
        #                                   default=200.0, minValue=0.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Matched Polygons')))

        self.addOutput(OutputVector(self.OUTPUT_CENTROID, self.tr('Projected Centroids')))

    def appendFields(self, layer, *fields):

        new_field_list = layer.fields().toList()

        for field in fields:
            unique_name = vector.createUniqueFieldName(field.name(), new_field_list)
            field.setName(unique_name)
            new_field_list.append(field)

        return new_field_list

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        centroid_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_CENTROIDS))
        pk_field = self.getParameterValue(self.INPUT_PK)
        line_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LINES))
        measure_field = self.getParameterValue(self.MEASURE_FIELD)
        line_pk_field = self.getParameterValue(self.LINE_PK)
        order_field = self.getParameterValue(self.ORDER_FIELD)
        ascending = self.getParameterValue(self.ASCENDING_ORDER)

        centroid_index = { f.attribute(pk_field): f.id() for f in centroid_layer.getFeatures() }
        line_index = QgsSpatialIndex(line_layer.getFeatures())

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            self.appendFields(layer,
                line_layer.fields()[vector.resolveFieldIndex(line_layer, line_pk_field)],
                QgsField(measure_field, QVariant.Double, len=10, prec=4)),
            layer.dataProvider().geometryType(),
            layer.crs())

        centroid_writer = self.getOutputFromName(self.OUTPUT_CENTROID).getVectorWriter(
            self.appendFields(layer,
                line_layer.fields()[vector.resolveFieldIndex(line_layer, line_pk_field)],
                QgsField(measure_field, QVariant.Double, len=10, prec=4)),
            centroid_layer.dataProvider().geometryType(),
            centroid_layer.crs())

        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            measure = 0.0
            closest = float('inf')
            closest_order = None
            closest_id = None

            pk = feature.attribute(pk_field)
            if not centroid_index.has_key(pk):
                continue

            centroid = centroid_layer.getFeatures(QgsFeatureRequest(centroid_index[pk])).next()
            closest_point = centroid.geometry()

            candidates = line_index.intersects(feature.geometry().boundingBox())
            q = QgsFeatureRequest().setFilterFids(candidates)

            for line in line_layer.getFeatures(q):

                if feature.geometry().intersects(line.geometry()):

                    order = line.attribute(order_field)
                    if ascending:
                        order = -order

                    projected_point = feature.geometry().intersection(line.geometry()).nearestPoint(centroid.geometry())
                    d = centroid.geometry().distance(projected_point)

                    if closest_order is None or order < closest_order:

                        closest_order = order

                        m = lineLocatePoint(line.geometry(), projected_point)
                        # if line is reversed
                        measure = line.attribute(measure_field) + (line.geometry().length() - m)
                        # else
                        # measure = line.attribute(measure_field) + m
                        closest = d
                        closest_id = line.attribute(line_pk_field)
                        # closest_point = line.geometry().interpolate(m)
                        closest_point = projected_point

                    elif order == closest_order and d < closest:

                        m = lineLocatePoint(line.geometry(), projected_point)
                        # if line is reversed
                        measure = line.attribute(measure_field) + (line.geometry().length() - m)
                        # else
                        # measure = line.attribute(measure_field) + m
                        closest = d
                        closest_id = line.attribute(line_pk_field)
                        # closest_point = line.geometry().interpolate(m)
                        closest_point = projected_point

            if closest_id is None:

                for line in line_layer.getFeatures():

                    projected_point = line.geometry().nearestPoint(centroid.geometry())
                    d = centroid.geometry().distance(projected_point)

                    if d < closest:

                        m = lineLocatePoint(line.geometry(), projected_point)
                        # if line is reversed
                        measure = line.attribute(measure_field) + (line.geometry().length() - m)
                        # else
                        # measure = line.attribute(measure_field) + m
                        closest = d
                        closest_id = line.attribute(line_pk_field)
                        # closest_point = line.geometry().interpolate(m)
                        closest_point = projected_point

            outfeature = QgsFeature()
            outfeature.setGeometry(feature.geometry())
            outfeature.setAttributes(feature.attributes() + [
                    closest_id,
                    measure
                ])
            writer.addFeature(outfeature)

            outcentroid = QgsFeature()
            outcentroid.setGeometry(closest_point)
            outcentroid.setAttributes(feature.attributes() + [
                    closest_id,
                    measure
                ])
            centroid_writer.addFeature(outcentroid)

            progress.setPercentage(int(current * total))