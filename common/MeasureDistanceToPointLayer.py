# -*- coding: utf-8 -*-

"""
***************************************************************************
    MeasureDistanceToPointLayer.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterString
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

class MeasureDistanceToPointLayer(GeoAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    DISTANCE_TO_LAYER = 'DISTANCE_TO_LAYER'
    DISTANCE_FIELD = 'DISTANCE_FIELD'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Measure Distance To Point Layer')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input Layer'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterVector(self.DISTANCE_TO_LAYER,
                                          self.tr('Distance To Layer'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterString(self.DISTANCE_FIELD,
                                          self.tr('Distance Field'), default='DISTANCE'))
        
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Measured')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        distance_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.DISTANCE_TO_LAYER))
        distance_field = self.getParameterValue(self.DISTANCE_FIELD)

        spatial_index = QgsSpatialIndex(distance_layer.getFeatures())

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.fields().toList() + [
                QgsField(distance_field, type=QVariant.Double, len=10, prec=2)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        total = 100.0 / layer.featureCount()
        for current, feature in enumerate(layer.getFeatures()):
            
            centroid = feature.geometry().centroid().asPoint()
            distance = -1
            for c in spatial_index.nearestNeighbor(centroid, 1):
                nearest = distance_layer.getFeatures(QgsFeatureRequest(c)).next()
                distance = feature.geometry().distance(nearest.geometry())

            feature.setAttributes(
                feature.attributes() + [
                    distance
                ])
            writer.addFeature(feature)

            progress.setPercentage(int(current * total))