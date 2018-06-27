# -*- coding: utf-8 -*-

"""
***************************************************************************
    JoinByNearest.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFeatureRequest, QgsFields
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from math import sqrt


class JoinByNearest(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    JOINED_LAYER = 'JOINED'
    OUTPUT_LAYER = 'OUTPUT'
    K_NEIGHBORS = 'K_NEIGHBORS'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Join By Nearest')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_ANY]))
        self.addParameter(ParameterVector(self.JOINED_LAYER,
                                          self.tr('Joined layer'), [ParameterVector.VECTOR_TYPE_ANY]))
        self.addParameter(ParameterNumber(self.K_NEIGHBORS,
                                          self.tr('Number of neighbors to search for'), 1, 20, 5, False))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('NearestJoin')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        joined = dataobjects.getObjectFromUri(self.getParameterValue(self.JOINED_LAYER))
        fields = layer.pendingFields().toList() + joined.pendingFields().toList()
        neighbors = self.getParameterValue(self.K_NEIGHBORS)

        layerFields = layer.fields()
        joinedFields = joined.fields()
        joinedFields = vector.testForUniqueness(layerFields, joinedFields)
        fields = layerFields.toList() + joinedFields.toList()
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields, layer.dataProvider().geometryType(), layer.crs())

        index = QgsSpatialIndex()
        for feature in vector.features(joined):
            index.insertFeature(feature)

        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):

            nearest = None
            distance = float('inf')
            geometry = feature.geometry()
            centroid = geometry.centroid().asPoint()

            nearests = index.nearestNeighbor(centroid, neighbors)
            q = QgsFeatureRequest().setFilterFids(nearests)
            for candidate in joined.getFeatures(q):
                d = geometry.distance(candidate.geometry())
                if d < distance:
                    distance = d
                    nearest = candidate
            
            if nearest:
                outFeature = QgsFeature()
                outFeature.setGeometry(geometry)
                outFeature.setAttributes(feature.attributes() + nearest.attributes())
                writer.addFeature(outFeature)

            progress.setPercentage(int(current * total))
