# -*- coding: utf-8 -*-

"""
***************************************************************************
    RandomPoints.py
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

from math import sqrt, floor


class RegularHexPoints(GeoAlgorithm):

    INPUT = 'INPUT'
    PK_FIELD = 'PK_FIELD'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Regular Hex Points From Polygons')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        
        self.addParameter(ParameterTableField(self.PK_FIELD,
                                          self.tr('Primary Key Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterNumber(self.DISTANCE,
                                          self.tr('Distance'),
                                          minValue=0.0, default=50.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Regular Hex Points')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        pk_field = self.getParameterValue(self.PK_FIELD)
        distance = self.getParameterValue(self.DISTANCE)
        h = 0.5*sqrt(3)*distance

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            [
                QgsField('PID', QVariant.Int, len=10),
                QgsField('X', QVariant.Double, len=10, prec=2),
                QgsField('Y', QVariant.Double, len=10, prec=2),
                vector_helper.resolveField(layer, pk_field)
            ],
            QGis.WKBPoint,
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)
        fid = 0

        for current, feature in enumerate(features):

            extent = feature.geometry().boundingBox()
            xmin = extent.xMinimum()
            ymin = extent.yMinimum()
            xmax = extent.xMaximum()
            ymax = extent.yMaximum()
            pk = feature.attribute(pk_field)

            baseline = True

            x0 = floor(xmin / distance) * distance
            y0 = floor(ymin / h) * h

            if y0 - h > ymin:

                y0 = y0 - h
                baseline = False

            if x0 - 0.5 * distance > xmin:
                x1 = x0 - 0.5 * distance
            else:
                x1 = x0 + 0.5 * distance

            y = y0

            while y < ymax:

                if baseline:
                    x = x0
                else:
                    x = x1

                while x < xmax:

                    geom = QgsGeometry.fromPoint(QgsPoint(x, y))

                    if feature.geometry().contains(geom):

                        fid = fid + 1
                        out_feature = QgsFeature()
                        out_feature.setAttributes([
                                fid,
                                x,
                                y,
                                pk
                            ])
                        out_feature.setGeometry(geom)
                        writer.addFeature(out_feature)

                    x = x + distance

                y = y + h
                baseline = not baseline

            progress.setPercentage(int(current * total))


