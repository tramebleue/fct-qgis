# -*- coding: utf-8 -*-

"""
***************************************************************************
    ProjectPointsAlongLine.py
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
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper
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
    vertices = line.asPolyline()

    for v0, v1 in zip(vertices[:-1], vertices[1:]):

        segment = QgsGeometry.fromPolyline([ v0, v1 ])
        d = segment.distance(point)

        if d < closest:
            closest = d
            closest_measure = measure + QgsGeometry.fromPoint(v0).distance(point)

        measure = measure + segment.length()

    return closest_measure

class ProjectPointsAlongLine(GeoAlgorithm):

    INPUT_POINTS = 'INPUT_POINTS'
    INPUT_LINES = 'INPUT_LINES'
    MEASURE_FIELD = 'MEASURE_FIELD'
    LINE_PK = 'LINE_PK'
    MAX_DISTANCE = 'MAX_DISTANCE'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Project Points Along Nearest Line')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_POINTS,
                                          self.tr('Input Points'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterVector(self.INPUT_LINES,
                                          self.tr('Measured Lines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.LINE_PK,
                                              self.tr('Line Primary Key'),
                                              parent=self.INPUT_LINES,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                          self.tr('Measure Field'),
                                          parent=self.INPUT_LINES,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterNumber(self.MAX_DISTANCE,
                                          self.tr('Maximum Distance'),
                                          default=200.0, minValue=0.0))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Projected Points')))

    def appendFields(self, layer, *fields):

        new_field_list = layer.fields().toList()

        for field in fields:
            unique_name = vector.createUniqueFieldName(field.name(), new_field_list)
            field.setName(unique_name)
            new_field_list.append(field)

        return new_field_list

    def processAlgorithm(self, progress):

        point_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_POINTS))
        line_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LINES))
        measure_field = self.getParameterValue(self.MEASURE_FIELD)
        line_pk_field = self.getParameterValue(self.LINE_PK)
        max_distance = self.getParameterValue(self.MAX_DISTANCE)

        line_index = QgsSpatialIndex(line_layer.getFeatures())

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                point_layer,
                vector_helper.resolveField(line_layer, line_pk_field),
                QgsField(measure_field, QVariant.Double, len=10, prec=4)
            ),
            point_layer.dataProvider().geometryType(),
            point_layer.crs())

        total = 100.0 / point_layer.featureCount()

        for current, feature in enumerate(point_layer.getFeatures()):

            measure = 0.0
            closest = float('inf')
            closest_id = None
            closest_point = feature.geometry()

            rect = feature.geometry().boundingBox()
            rect.grow(max_distance)

            candidates = line_index.intersects(rect)
            q = QgsFeatureRequest().setFilterFids(candidates)

            for line in line_layer.getFeatures(q):

                d = line.geometry().distance(feature.geometry())
                if d < closest:
                    m = lineLocatePoint(line.geometry(), feature.geometry())
                    # if line is reversed
                    measure = line.attribute(measure_field) + (line.geometry().length() - m)
                    # else
                    # measure = line.attribute(measure_field) + m
                    closest = d
                    closest_id = line.attribute(line_pk_field)
                    closest_point = line.geometry().interpolate(m)

            if closest_id is not None:

                outfeature = QgsFeature()
                outfeature.setGeometry(closest_point)
                outfeature.setAttributes(feature.attributes() + [
                        closest_id,
                        measure
                    ])
                writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))