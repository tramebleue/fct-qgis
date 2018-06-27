# -*- coding: utf-8 -*-

"""
***************************************************************************
    SplitLine.py
    ---------------------
    Date                 : November 2016
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
__date__ = 'November 2016'
__copyright__ = '(C) 2016, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QgsFeature, QgsGeometry, QgsPoint
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from math import sqrt


class SplitLine(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    MAXLENGTH = 'MAXLENGTH'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Split Lines')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterNumber(self.MAXLENGTH,
                                          self.tr('Maximum length'), 0, None, 1, False))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Splitted')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.pendingFields().toList(), layer.dataProvider().geometryType(), layer.crs())
        maxlength = self.getParameterValue(self.MAXLENGTH)

        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):

            geometry = feature.geometry()

            if geometry.isMultipart():

                multilinestring = geometry.asMultiPolyline()
                splitml = []
                for linestring in multilinestring:
                    points = self.split(linestring, maxlength)
                    splitml.append(points)
                outFeature = QgsFeature()
                outFeature.setAttributes(feature.attributes())
                outFeature.setGeometry(QgsGeometry.fromMultiPolyline(splitml))
                writer.addFeature(outFeature)

            else:

                linestring = geometry.asPolyline()
                points = self.split(linestring, maxlength)
                outFeature = QgsFeature()
                outFeature.setAttributes(feature.attributes())
                outFeature.setGeometry(QgsGeometry.fromPolyline(points))
                writer.addFeature(outFeature)

            progress.setPercentage(int(current * total))

    def distance(self, p1, p2):
        # return sqrt(p1.sqrDist(p2))
        return sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

    def split(self, linestring, maxlength):

        p1 = linestring[0]
        points = []
        for p2 in linestring[1:]:
            length = self.distance(p1, p2)
            if length == 0:
                p1 = p2
                continue
            k = 0
            step = maxlength / length
            s = k*step
            x0 = p1[0]
            y0 = p1[1]
            a = p2[0] - x0
            b = p2[1] - y0
            while (s < 1):
                x = x0 + s*a
                y = y0 + s*b
                points.append(QgsPoint(x,y))
                k = k+1
                s = k*step
            points.append(p2)
            p1 = p2
        if not points:
            points = [ linestring[0], linestring[-1] ]
        return points
