# -*- coding: utf-8 -*-

"""
***************************************************************************
    UpdateFrictionCost.py
    ---------------------
    Date                 : February 2018
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTable, ParameterTableField
from processing.core.outputs import OutputVector, OutputTable
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

class ComputeFrictionCost(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    # TARGET_FIELD = 'TARGET_FIELD'
    FRICTION_LAYER = 'FRICTION_LAYER'

    COST_TABLE = 'COST_TABLE'
    CLASS_FIELD = 'CLASS_FIELD'
    COST_FIELD = 'COST_FIELD'
    MODE = 'MODE'

    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Compute Friction Cost')
        self.group, self.i18n_group = self.trAlgorithm('Graph Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Source Layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        # self.addParameter(ParameterTableField(self.TARGET_FIELD,
        #                                   self.tr('Target Field'),
        #                                   parent=self.INPUT_LAYER,
        #                                   datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.FRICTION_LAYER,
                                          self.tr('Friction Layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterTableField(self.CLASS_FIELD,
                                          self.tr('Class Field'),
                                          parent=self.FRICTION_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addParameter(ParameterTable(self.COST_TABLE,
                                          self.tr('Cost Table'), optional=False))

        self.addParameter(ParameterTableField(self.COST_FIELD,
                                          self.tr('Cost Field'),
                                          parent=self.COST_TABLE,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterSelection(self.MODE,
                                             self.tr('Cost Aggregation'),
                                             options=[self.tr('Weighted by Length'), self.tr('Maximum')], default=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Friction Costs')))

    def processAlgorithm(self, progress):

        progress.setText(self.tr("Load costs table ..."))

        costs = dict()
        max_cost = 0.0
        cost_table = dataobjects.getObjectFromUri(self.getParameterValue(self.COST_TABLE))
        class_field = self.getParameterValue(self.CLASS_FIELD)
        cost_field = self.getParameterValue(self.COST_FIELD)
        mode_weighted = (self.getParameterValue(self.MODE) == 0)
        
        for record in cost_table.getFeatures():

            class_value = record.attribute(class_field)
            cost = record.attribute(cost_field)
            if cost > max_cost:
                max_cost = cost
            costs[class_value] = cost

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Set max cost tos %s" % max_cost)

        progress.setText(self.tr("Build friction layer index ..."))

        friction_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.FRICTION_LAYER))
        friction_index = QgsSpatialIndex(friction_layer.getFeatures())

        progress.setText(self.tr("Compute and update friction costs ..."))

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))

        total = 100.0 / layer.featureCount()
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList() + [
                QgsField(cost_field, type=QVariant.Double, len=10, prec=2)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        for current, feature in enumerate(layer.getFeatures()):

            cost = 0

            for match_id in friction_index.intersects(feature.geometry().boundingBox()):
                
                match = friction_layer.getFeatures(QgsFeatureRequest(match_id)).next()
                
                if feature.geometry().intersects(match.geometry()):

                    friction_class = match.attribute(class_field)
                    intersection = feature.geometry().intersection(match.geometry())

                    if mode_weighted:
                        cost = cost + intersection.length() * costs.get(friction_class, max_cost)
                    else:
                        cost = max(cost, costs.get(friction_class, max_cost))

            outfeature = QgsFeature()
            outfeature.setAttributes(
                    feature.attributes() + [
                        cost
                    ]
                )
            outfeature.setGeometry(feature.geometry())
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))