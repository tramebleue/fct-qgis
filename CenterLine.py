# -*- coding: utf-8 -*-

"""
***************************************************************************
    CenterLine.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog

class CenterLine(GeoAlgorithm):

    INPUT_POLYLINES = 'INPUT_POLYLINES'
    INPUT_POLYGONS = 'INPUT_POLYGONS'
    DISAGGREGATION_STEP = 'DISAGGREGATION_STEP'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Center Line')
        self.group, self.i18n_group = self.trAlgorithm('Main')

        self.addParameter(ParameterVector(self.INPUT_POLYLINES,
                                          self.tr('Input lines'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_POLYGONS,
                                          self.tr('Input polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterNumber(self.DISAGGREGATION_STEP,
                                          self.tr('Disaggregation step'), default=50, minValue=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Center line')))

    def processAlgorithm(self, progress):
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Extract polyline end points ...')
        ExtremePoints = Processing.runAlgorithm('fluvialtoolbox:extremepoints', None,
                            {
                                'INPUT': self.getParameterValue(self.INPUT_POLYLINES)
                            })

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Convert polylines to polygons ...')
        PolyToLine = Processing.runAlgorithm('qgis:polygonstolines', None,
                            {
                                'INPUT': self.getParameterValue(self.INPUT_POLYGONS)
                            })

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Find nearest objects ...')
        NearTable = Processing.runAlgorithm('fluvialtoolbox:neartable', None,
                            {
                                'FROM': ExtremePoints.getOutputValue('OUTPUT'),
                                'FROM_ID_FIELD': 'FID',
                                'TO': PolyToLine.getOutputValue('OUTPUT'),
                                'TO_ID_FIELD': 'FID',
                                'NEIGHBORS': 1,
                                'SEARCH_DISTANCE': 0
                            })

        # Split PolyToLine with ExtremePoints
        # Number lines (UGO_ID) in PolyToLine
        # Split lines in PolyToLine w.r.t DISAGGREGATION_STEP
        # Extract Points
        # Compute Thiessen polygons
        # Dissolve (merge) by UGO_ID
        # Intersect with INPUT_POLYGONS
        # Convert to linestring
        # Keep interior linestrings
        # Delete identical linestrings
        # Simplify and smooth result
