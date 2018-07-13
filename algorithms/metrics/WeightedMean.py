# -*- coding: utf-8 -*-

"""
***************************************************************************
    WeightedMean.py
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

from qgis.core import QgsFeature, QgsField, QgsPoint, QgsGeometry
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper
from collections import defaultdict

class WeightedMean(GeoAlgorithm):

    INPUT = 'INPUT'
    TARGET = 'TARGET'
    METRIC_FIELD = 'METRIC_FIELD'
    INPUT_FK_FIELD = 'INPUT_FK_FIELD'
    TARGET_PK_FIELD = 'TARGET_PK_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Weighted Mean')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Metrics (Polyline)'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.METRIC_FIELD,
                                          self.tr('Metric Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.INPUT_FK_FIELD,
                                          self.tr('Group Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addParameter(ParameterVector(self.TARGET,
                                          self.tr('Target Objects'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterTableField(self.TARGET_PK_FIELD,
                                          self.tr('Id Field'),
                                          parent=self.TARGET,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Weighted Mean')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        target = dataobjects.getObjectFromUri(self.getParameterValue(self.TARGET))
        metric_field = self.getParameterValue(self.METRIC_FIELD)
        fk_field = self.getParameterValue(self.INPUT_FK_FIELD)
        pk_field = self.getParameterValue(self.TARGET_PK_FIELD)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                target,
                vector_helper.resolveField(layer, metric_field)
            ),
            target.dataProvider().geometryType(),
            target.crs())

        progress.setText(self.tr('Build input index ...'))

        features = vector.features(layer)
        total = 100.0 / len(features)

        values = defaultdict(lambda: (0.0, 0.0))

        for current, feature in enumerate(features):

            key = feature.attribute(fk_field)
            metric = feature.attribute(metric_field)
            weight = feature.geometry().length()

            value, cum_weight = values[key]
            values[key] = (value + weight * metric, cum_weight + weight)

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Aggregate value by target key ...'))

        total = 100.0 / target.featureCount()

        for current, feature in enumerate(target.getFeatures()):

            key = feature.attribute(pk_field)
            value, cum_weight = values[key]

            if cum_weight > 0.0:
                value = value / cum_weight
            else:
                value = None

            out_feature = QgsFeature()
            out_feature.setGeometry(feature.geometry())
            out_feature.setAttributes(feature.attributes() + [
                    value
                ])
            writer.addFeature(out_feature)

            progress.setPercentage(int(current * total))