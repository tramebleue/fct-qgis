# -*- coding: utf-8 -*-

"""
***************************************************************************
    NearTable.py
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

from PyQt4.QtCore import QVariant
from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from qgis.core import QgsSpatialIndex, QgsFields, QgsField, QgsFeatureRequest
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector, OutputNumber
from processing.tools import dataobjects, vector
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper

class NearTable(GeoAlgorithm):

    FROM_LAYER = 'FROM'
    FROM_ID_FIELD = 'FROM_ID_FIELD'
    TO_LAYER = 'TO'
    TO_ID_FIELD = 'TO_ID_FIELD'
    OUTPUT = 'OUTPUT'
    NEIGHBORS = 'NEIGHBORS'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    MAX_DISTANCE = 'MAX_DISTANCE'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Near Table')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        self.addParameter(ParameterVector(self.FROM_LAYER,
                                          self.tr('Source points layer'), [ParameterVector.VECTOR_TYPE_POINT]))
        self.addParameter(ParameterTableField(self.FROM_ID_FIELD,
                                              self.tr('Source ID field'),
                                              self.FROM_LAYER,
                                              optional=True))
        self.addParameter(ParameterVector(self.TO_LAYER,
                                          self.tr('Destination layer'), [ParameterVector.VECTOR_TYPE_ANY]))
        self.addParameter(ParameterTableField(self.TO_ID_FIELD,
                                              self.tr('Destination ID field'),
                                              self.TO_LAYER,
                                              optional=True))
        self.addParameter(ParameterNumber(self.NEIGHBORS,
                                          self.tr('Neighbors count'), default=1, minValue=1))
        self.addParameter(ParameterNumber(self.SEARCH_DISTANCE,
                                          self.tr('Search distance'), default=0, minValue=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Near table')))
        self.addOutput(OutputNumber(self.MAX_DISTANCE, self.tr('Maximum distance')))

    def processAlgorithm(self, progress):

        neighbors = self.getParameterValue(self.NEIGHBORS)
        search_distance = self.getParameterValue(self.SEARCH_DISTANCE)
        max_distance = 0

        to_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.TO_LAYER))
        to_id_field = self.getParameterValue(self.TO_ID_FIELD) or 0
        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.FROM_LAYER))
        id_field = self.getParameterValue(self.FROM_ID_FIELD) or 0

        features = vector.features(layer)
        to_features = vector.features(to_layer)
        total = 100.0 / (len(features) + len(to_features))
        current = 0

        index = QgsSpatialIndex()
        for feature in vector.features(to_layer):
            index.insertFeature(feature)
            current += 1
            progress.setPercentage(int(current * total))

        fields = QgsFields()
        fields.append(QgsField('SOURCE_ID', vector_helper.resolveField(layer, id_field).type()))
        fields.append(QgsField('NEAR_ID', vector_helper.resolveField(to_layer, to_id_field).type()))
        fields.append(QgsField('NEAR_DIST', QVariant.Double))
        fields.append(QgsField('NEAR_RANK', QVariant.Int))
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            fields.toList(), QGis.WKBPoint, layer.crs())

        for feature in features:
            p = feature.geometry().asPoint()
            for rank, nearestID in enumerate(index.nearestNeighbor(p, neighbors)):
                query = QgsFeatureRequest().setFilterFid(nearestID)
                nearest = to_layer.getFeatures(query).next()
                distance = feature.geometry().distance(nearest.geometry())
                if search_distance == 0 or distance > search_distance:
                    record = QgsFeature()
                    record.setFields(fields)
                    record.setAttribute('SOURCE_ID', feature.attribute(id_field))
                    record.setAttribute('NEAR_ID', nearest.attribute(to_id_field))
                    record.setAttribute('NEAR_DIST', distance)
                    record.setAttribute('NEAR_RANK', rank)
                    record.setGeometry(QgsGeometry.fromPoint(p))
                    writer.addFeature(record)
                    if distance > max_distance:
                        max_distance = distance
            current += 1
            progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Maximum distance : %f' % max_distance)
        self.setOutputValue(self.MAX_DISTANCE, max_distance)
