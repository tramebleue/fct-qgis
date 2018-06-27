# -*- coding: utf-8 -*-

"""
***************************************************************************
    UniqueValuesTable.py
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
from processing.core.outputs import OutputVector, OutputTable
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

class UniqueValuesTable(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    VALUE_FIELD = 'VALUE_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Unique Values')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Source Layer'), [ParameterVector.VECTOR_TYPE_ANY]))
        
        self.addParameter(ParameterTableField(self.VALUE_FIELD,
                                          self.tr('Source Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addOutput(OutputTable(self.OUTPUT, self.tr('Unique Values')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        field_name = self.getParameterValue(self.VALUE_FIELD)
        values = dict()

        total = 100.0 / layer.featureCount()
        for current, feature in enumerate(layer.getFeatures()):

            value = feature.attribute(field_name)
            
            if not values.has_key(value):
                values[value] = 1
            else:
                values[value] = values[value] + 1

            progress.setPercentage(int(current * total))

        writer = self.getOutputFromName(self.OUTPUT).getTableWriter([
                field_name,
                'COUNT'
            ])

        for record in values.items():

            writer.addRecord(record)

        # field = layer.fields().toList()[ layer.fieldNameIndex(field_name) ]
        # writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
        #         [
        #             field,
        #             QgsField('COUNT', type=QVariant.Int, len=6)
        #         ],
        #         QGis.WKBNoGeometry,
        #         layer.crs()
        #     )

        # for value, cnt in values.items():
        #     record = QgsFeature()
        #     record.setAttributes([
        #             value,
        #             cnt
        #         ])
        #     writer.addFeature(record)