# -*- coding: utf-8 -*-

"""
***************************************************************************
    PathLengthOrder.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField
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

class SelectFullLengthPaths(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    PATHID_FIELD = 'PATHID_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Select Full Length Paths')
        self.group, self.i18n_group = self.trAlgorithm('Graph Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.PATHID_FIELD,
                                          self.tr('PathId Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        pathid_field = self.getParameterValue(self.PATHID_FIELD)

        if layer.selectedFeatureCount() == 0:
            return

        # Step 1

        progress.setText(self.tr("Build path index ..."))
        paths = set()

        total = 100.0 / layer.selectedFeatureCount()
        for current, feature in enumerate(layer.selectedFeatures()):
            
            pathid = feature.attribute(pathid_field)
            paths.add(pathid)
            progress.setPercentage(int(current * total))

        # Step 2

        progress.setText(self.tr("Build path index ..."))
        total = 100.0 / layer.featureCount()
        selection = list()
        for current, feature in enumerate(layer.getFeatures()):

            pathid = feature.attribute(pathid_field)
            if pathid in paths:
                selection.append(feature.id())

        layer.setSelectedFeatures(selection)

