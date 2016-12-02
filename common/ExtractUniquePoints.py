# -*- coding: utf-8 -*-

"""
***************************************************************************
    ExtractUniquePoints.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

class ExtractUniquePoints(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Extract Unique Points')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addOutput(OutputVector(self.OUTPUT, self.tr('Unique points')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter([], QGis.WKBPoint, layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        points = set()
        vertices = 0

        for current, feature in enumerate(features):

            geometry = feature.geometry()
            if geometry.isMultipart():
                for polyline in geometry.asMultiPolyline():
                    points.add(polyline[0])
                    points.add(polyline[-1])
                    vertices = vertices + 2
            else:
                polyline = geometry.asPolyline()
                points.add(polyline[0])
                points.add(polyline[-1])
                vertices = vertices + 2

            progress.setPercentage(int(current * total))

        total = 100.0 / len(points)
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Extracting %d out of %d vertices' % (len(points), vertices))


        for p in points:
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPoint(p))
            writer.addFeature(feature)
            progress.setPercentage(int(current * total))
