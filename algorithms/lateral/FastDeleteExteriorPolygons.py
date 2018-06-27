# -*- coding: utf-8 -*-

"""
***************************************************************************
    FastDeleteExteriorPolygons.py
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
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

class FastDeleteExteriorPolygons(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    REFERENCE_LAYER = 'REFERENCE_LAYER'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Fast Delete Exterior Polygons')
        self.group, self.i18n_group = self.trAlgorithm('Lateral Continuity')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Polygon Layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterVector(self.REFERENCE_LAYER,
                                          self.tr('Reference Layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        reference = dataobjects.getObjectFromUri(self.getParameterValue(self.REFERENCE_LAYER))

        layer.startEditing()
        total = 100.0 / layer.featureCount()
        deleted = 0

        for current, feature in enumerate(layer.getFeatures()):

            centroid = feature.geometry().centroid()
            contained = False

            for ref in reference.getFeatures():
                if ref.geometry().contains(centroid):
                    contained = True
                    break

            if not contained:
                layer.deleteFeature(feature.id())
                deleted = deleted + 1

            progress.setPercentage(int(current * total))

        layer.commitChanges()
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Deleted %d features" % deleted)