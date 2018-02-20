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
from math import sqrt

class ProjectPointsAlongLine(GeoAlgorithm):

    INPUT_POINTS = 'INPUT_POINTS'
    INPUT_LINES = 'INPUT_LINES'
    MEASURE_FIELD = 'MEASURE_FIELD'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Project Points Along Line')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_POINTS,
                                          self.tr('Input Points'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterVector(self.INPUT_LINES,
                                          self.tr('Measured Lines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                          self.tr('Measure Field'),
                                          parent=self.INPUT_LINES,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Projected Points')))

    def lineLocatePoint(self, line, point):

        vertices = iter(line.asPolyline())
        v0 = next(vertices)

        measure = 0.0
        closest = float('inf')
        closest_measure = 0.0

        for v1 in vertices:

            segment = QgsGeometry.fromPolyline([ v0, v1 ])
            d = segment.distance(point)
            if d < closest:
                closest = d
                closest_measure = measure + QgsGeometry.fromPoint(v0).distance(point)

            measure = measure + segment.length()
            v0 = v1

        return closest_measure

    def processAlgorithm(self, progress):

        point_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_POINTS))
        line_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LINES))
        measure_field = self.getParameterValue(self.MEASURE_FIELD)

        line_index = QgsSpatialIndex(line_layer.getFeatures())

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            point_layer.fields().toList() + [
                QgsField(measure_field, QVariant.Double, len=10, prec=4)
            ],
            point_layer.dataProvider().geometryType(),
            point_layer.crs())
        total = 100.0 / point_layer.featureCount()

        for current, feature in enumerate(point_layer.getFeatures()):

            measure = 0.0
            closest = float('inf')
            closest_point = feature.geometry()

            for line in vector.features(line_layer):

                d = line.geometry().distance(feature.geometry())
                if d < closest:
                    m = self.lineLocatePoint(line.geometry(), feature.geometry())
                    # if line is reversed
                    measure = line.attribute(measure_field) + (line.geometry().length() - m)
                    # else
                    # measure = line.attribute(measure_field) + m
                    closest = d
                    closest_point = line.geometry().interpolate(m)

            outfeature = QgsFeature()
            outfeature.setGeometry(closest_point)
            outfeature.setAttributes(feature.attributes() + [
                    measure
                ])
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))