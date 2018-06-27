# -*- coding: utf-8 -*-

"""
***************************************************************************
    SelectNearestFeature.py
    ---------------------
    Date                 : March 2018
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
__date__ = 'March 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField
from qgis.core import QgsVectorLayer
from qgis.core import QgsRectangle
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

class SelectNearestFeature(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    REFERENCE_LAYER = 'REFERENCE_LAYER'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Select Nearest Feature')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Select In Layer'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterVector(self.REFERENCE_LAYER,
                                          self.tr('Reference Layer'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterNumber(self.SEARCH_DISTANCE,
                                          self.tr('Search Distance'), minValue=0.0))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        reference_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.REFERENCE_LAYER))
        search_distance = self.getParameterValue(self.SEARCH_DISTANCE)

        layer_index = QgsSpatialIndex(layer.getFeatures())
        ref_features = vector.features(reference_layer)

        total = 100.0 / len(ref_features)
        selection = set()

        for current, ref_feature in enumerate(ref_features):
            
            ref_geometry = ref_feature.geometry()
            search_box = QgsRectangle(ref_geometry.boundingBox())
            search_box.grow(search_distance)
            distance = float('inf')
            nearest_id = None

            for candidate_id in layer_index.intersects(search_box):

                candidate = layer.getFeatures(QgsFeatureRequest(candidate_id)).next()
                d = candidate.geometry().distance(ref_geometry)
                if d < distance:
                    nearest_id = candidate_id
                    distance = d

            if nearest_id is not None:
                selection.add(nearest_id)

            progress.setPercentage(int(current * total))

        layer.setSelectedFeatures(list(selection))