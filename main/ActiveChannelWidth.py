# -*- coding: utf-8 -*-

"""
***************************************************************************
    ActiveChannelWidth.py
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

from PyQt4.QtCore import QSettings
from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from qgis.core import QgsFeatureRequest, QgsExpression, QgsVectorFileWriter
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.tools.system import getTempFilenameInTempFolder
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog

class ActiveChannelWidth(GeoAlgorithm):

    INPUT_POLYLINES = 'INPUT_POLYLINES'
    INPUT_POLYGONS = 'INPUT_POLYGONS'
    DISAGGREGATION_STEP = 'DISAGGREGATION_STEP'
    OUTPUT = 'OUTPUT'

    STEPS = 16

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Active Channel Width')
        self.group, self.i18n_group = self.trAlgorithm('Main')

        self.addParameter(ParameterVector(self.INPUT_POLYLINES,
                                          self.tr('Input lines'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_POLYGONS,
                                          self.tr('Input polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterNumber(self.DISAGGREGATION_STEP,
                                          self.tr('Disaggregation step'), default=50, minValue=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Center line')))

    def nextStep(self, description, progress):
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, description)
        progress.setPercentage(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1


    def processAlgorithm(self, progress):
        pass