# -*- coding: utf-8 -*-

"""
***************************************************************************
    SplitLineString.py
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

from PyQt4.QtCore import QVariant
from qgis.core import QgsExpression, QgsFeatureRequest, QgsFeature, QgsGeometry
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterTableField
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterString
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog


class CleanValleyBottom(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FIELD = 'FIELD'
    VALUE = 'VALUE'
    MIN_AREA = 'MIN_AREA'
    MIN_HOLE_AREA = 'MIN_HOLE_AREA'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Clean Valley Bottom')
        self.group, self.i18n_group = self.trAlgorithm('Main')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterTableField(self.FIELD,
                                              self.tr('Selection field'), self.INPUT))
        self.addParameter(ParameterNumber(self.VALUE,
                                          self.tr('Selection value'), 0.0, 99999999.999999, 1))
        self.addParameter(ParameterNumber(self.MIN_AREA,
                                          self.tr('Minimum polygon area'), 0.0, 99999999.999999, 50e4))
        self.addParameter(ParameterNumber(self.MIN_HOLE_AREA,
                                          self.tr('Minimum hole area'), 0.0, 99999999.999999, 10e4))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Output layer')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
                layer.pendingFields(),
                layer.dataProvider().geometryType(),
                layer.dataProvider().crs())

        expression = QgsExpression("%s = %f" %
                        (self.getParameterValue(self.FIELD),
                         self.getParameterValue(self.VALUE)))
        features = vector.features(layer)

        min_area = self.getParameterValue(self.MIN_AREA)
        min_hole_area = self.getParameterValue(self.MIN_HOLE_AREA)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):
            
            geom = feature.geometry()
            
            if expression.evaluate(feature) and geom.area() >= min_area:
            
                newFeature = QgsFeature()
                newFeature.setAttributes(feature.attributes())
                
                if geom.isMultipart():
                    parts = geom.asMultiPolygon()
                    newParts = []
                    for part in parts:
                        newPart = [ part[0] ]
                        for ring in part[1:]:
                            if QgsGeometry.fromPolygon([ ring ]).area() >= min_hole_area:
                                newPart.append(ring)
                        newParts.append(newPart)
                    newGeom = QgsGeometry.fromMultiPolygon(newParts)
                    newFeature.setGeometry(newGeom)
                
                else:
                    rings = geom.asPolygon()
                    newRings = [ rings[0] ]
                    for ring in rings[1:]:
                        if QgsGeometry.fromPolygon([ ring ]).area() >= min_hole_area:
                            newRings.append(ring)
                    newGeom = QgsGeometry.fromPolygon(newRings)
                    newFeature.setGeometry(newGeom)
                
                writer.addFeature(newFeature)
            
            progress.setPercentage(int(current * total))

        del writer
