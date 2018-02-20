# -*- coding: utf-8 -*-

"""
***************************************************************************
    ValleyBottomWidth.py
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
from processing.gui.Postprocessing import handleAlgorithmResults

class ValleyBottomWidth(GeoAlgorithm):

    INPUT_POLYGONS = 'INPUT'
    INPUT_CENTERLINE = 'CENTERLINE'
    DISAGGREGATION_STEP = 'DISAGGREGATION_STEP'
    OUTPUT = 'OUTPUT'

    STEPS = 17

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Valley Bottom Width')
        self.group, self.i18n_group = self.trAlgorithm('Attic')

        self.addParameter(ParameterVector(self.INPUT_POLYGONS,
                                          self.tr('Input polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterVector(self.INPUT_CENTERLINE,
                                          self.tr('Centerline'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterNumber(self.DISAGGREGATION_STEP,
                                          self.tr('Disaggregation step'), default=50, minValue=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Valley Bottom Width')))

    def nextStep(self, description, progress):
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, description)
        progress.setText(description)
        progress.setPercentage(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1

    def handleResult(self, description):
        def _handle(alg, *args, **kw):
            if self.display_result:
                for out in alg.outputs:
                    out.description = description
                handleAlgorithmResults(alg, *args, **kw)
        return _handle


    def processAlgorithm(self, progress):

        SIMPLIFY_TOLERANCE = 10

        disaggregation_step = self.getParameterValue(self.DISAGGREGATION_STEP)
        self.current_step = 0
        self.display_result = True

        # Converto polygon to countour line

        self.nextStep('Simplify polygons ...', progress)
        SimplifiedPolygons = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': self.getParameterValue(self.INPUT_POLYGONS),
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })

        self.nextStep('Convert polylines to polygons ...', progress)
        ContourLine = Processing.runAlgorithm('qgis:polygonstolines', None,
                            {
                                'INPUT': SimplifiedPolygons.getOutputValue('OUTPUT')
                            })

        # Split contour w.r.t disaggregation step
        
        self.nextStep('Split lines w/ disaggregation step ...', progress)
        SplittedContourLine = Processing.runAlgorithm('fluvialtoolbox:splitlines', None,
                            {
                              'INPUT': ContourLine.getOutputValue('OUTPUT'),
                              'MAXLENGTH': disaggregation_step
                            })

        # Convert contour to points

        self.nextStep('Extract contour points ...', progress)
        ContourPoints = Processing.runAlgorithm('qgis:extractnodes', self.handleResult('Contour Points'),
                            {
                                'INPUT': SplittedContourLine.getOutputValue('OUTPUT')
                            })

        # Compute vicinity  table from contour points to center line
        
        self.nextStep('Split center line ...', progress)
        SplittedCenterLine = Processing.runAlgorithm('fluvialtoolbox:splitlines', None,
                            {
                              'INPUT': self.getParameterValue(self.INPUT_CENTERLINE),
                              'MAXLENGTH': disaggregation_step
                            })

        self.nextStep('Extract center line points ...', progress)
        CenterLinePoints = Processing.runAlgorithm('qgis:extractnodes', self.handleResult('Center Line Points'),
                            {
                                'INPUT': SplittedCenterLine.getOutputValue('OUTPUT')
                            })

        self.nextStep('Compute vicinity table', progress)
        NearTable = Processing.runAlgorithm('fluvialtoolbox:neartable', None,
                            {
                                'FROM': CenterLinePoints.getOutputValue('OUTPUT'),
                                'FROM_ID_FIELD': 'FID',
                                'TO': ContourPoints.getOutputValue('OUTPUT'),
                                'TO_ID_FIELD': 'FID',
                                'NEIGHBORS': 1,
                                'SEARCH_DISTANCE': 0
                            })

        # self.nextStep('Remove unnecessary fields', progress)
        self.setOutputValue(self.OUTPUT, NearTable.getOutputValue('OUTPUT'))
