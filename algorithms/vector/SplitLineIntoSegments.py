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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from math import sqrt


class SplitLineIntoSegments(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Split Lines Into Segments')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Segments')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.pendingFields().toList(), QGis.WKBLineString, layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):

            geometry = feature.geometry()

            if geometry.isMultipart():

                multilinestring = geometry.asMultiPolyline()
                for linestring in multilinestring:
                    for i in xrange(0, len(linestring)-1):
                        points = linestring[i:i+2]
                        outFeature = QgsFeature()
                        outFeature.setAttributes(feature.attributes())
                        outFeature.setGeometry(QgsGeometry.fromPolyline(points))
                        writer.addFeature(outFeature)

            else:

                linestring = geometry.asPolyline()
                for i in xrange(0, len(linestring)-1):
                    points = linestring[i:i+2]
                    outFeature = QgsFeature()
                    outFeature.setAttributes(feature.attributes())
                    outFeature.setGeometry(QgsGeometry.fromPolyline(points))
                    writer.addFeature(outFeature)

            progress.setPercentage(int(current * total))
