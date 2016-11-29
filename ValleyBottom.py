# -*- coding: utf-8 -*-

"""
***************************************************************************
    SplitLineString.py
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

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults


class ValleyBottom(GeoAlgorithm):

    INPUT_DEM = 'INPUT_DEM'
    INPUT_NETWORK = 'INPUT_NETWORK'
    INPUT_ZOI = 'INPUT_ZOI'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Valley Bottom')
        self.group, self.i18n_group = self.trAlgorithm('Main')

        self.addParameter(ParameterRaster(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(ParameterVector(self.INPUT_NETWORK,
                                          self.tr('Input Stream Network'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_ZOI,
                                          self.tr('Zone of Interest'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Valley Bottom')))

    def processAlgorithm(self, progress):

        current = 0
        steps = 18
        total = 100.0 / steps
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Clip stream network by ZOI ...')
        ClippedNetwork = Processing.runAlgorithm('qgis:clip', None,
                            {
                              'INPUT': self.getParameterValue(self.INPUT_NETWORK),
                              'OVERLAY': self.getParameterValue(self.INPUT_ZOI)
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Simplify network')
        SimplifiedNetwork = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': ClippedNetwork.getOutputValue('OUTPUT'),
                              'TOLERANCE': 20
                            })
        current = current + 1
        progress.setPercentage(int(current * total))
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Split network ...')
        SplittedNetwork = Processing.runAlgorithm('fluvialtoolbox:splitlinestring', None,
                            {
                              'INPUT': SimplifiedNetwork.getOutputValue('OUTPUT'),
                              'MAXLENGTH': 50
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Extract points ...')
        NetworkPoints = Processing.runAlgorithm('qgis:extractnodes', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT')
                            })
        current = current + 1
        progress.setPercentage(int(current * total))
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute large buffer ...')
        LargeBuffer = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT'),
                              'DISTANCE': 1000,
                              'DISSOLVE': True
                            })
        current = current + 1
        progress.setPercentage(int(current * total))
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute small buffer ...')
        SmallBuffer = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT'),
                              'DISTANCE': 50,
                              'DISSOLVE': True
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute thiessen polygons ...')
        ThiessenPolygons = Processing.runAlgorithm('qgis:voronoipolygons', None,
                            {
                              'INPUT': NetworkPoints.getOutputValue('OUTPUT'),
                              'BUFFER': 50.0
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Clip thiessen polygons ...')
        ClippedThiessenPolygons = Processing.runAlgorithm('qgis:clip', None,
                            {
                              'INPUT': ThiessenPolygons.getOutputValue('OUTPUT'),
                              'OVERLAY': LargeBuffer.getOutputValue('OUTPUT')
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Clip DEM ...')
        ClippedDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', None,
                            {
                              'INPUT': self.getParameterValue(self.INPUT_DEM),
                              'MASK': LargeBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': 3,
                              'TILED': True
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Extract minimum DEM ...')
        MinDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', None,
                            {
                              'INPUT': ClippedDEM.getOutputValue('OUTPUT'),
                              'MASK': SmallBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': False,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': 3,
                              'TILED': True
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute reference elevation for every polygon ...')
        ReferencePolygons = Processing.runAlgorithm('qgis:zonalstatistics', None,
                            {
                              'INPUT_RASTER': MinDEM.getOutputValue('OUTPUT'),
                              'RASTER_BAND': 1,
                              'INPUT_VECTOR': ClippedThiessenPolygons.getOutputValue('OUTPUT'),
                              'COLUMN_PREFIX': '_',
                              'GLOBAL_EXTENT': False
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Convert to reference DEM ...')
        ReferenceDEM = Processing.runAlgorithm('gdalogr:rasterize', None,
                            {
                              'INPUT': ReferencePolygons.getOutputValue('OUTPUT_LAYER'),
                              'FIELD': '_median',
                              'TILED': True,
                              'COMPRESS': 3,
                              'DIMENSIONS': 1,
                              'WIDTH': 5,
                              'HEIGHT': 5,
                              'EXTRA': '-tap'
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute relative DEM and extract bottom ...')
        ValleyBottomRaster = Processing.runAlgorithm('fluvialtoolbox:valleybottommask', None,
                            {
                              'INPUT_DEM': ClippedDEM.getOutputValue('OUTPUT'),
                              'REFERENCE_DEM': ReferenceDEM.getOutputValue('OUTPUT'),
                              'MIN_THRESHOLD': -10,
                              'MAX_THRESHOLD': 10,
                            })
        current = current + 1
        progress.setPercentage(int(current * total))


        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Sieve result ...')
        SievedValleyBottomRaster = Processing.runAlgorithm('gdalogr:sieve', None,
                            {
                              'INPUT': ValleyBottomRaster.getOutputValue('OUTPUT'),
                              'THRESHOLD': 40,
                              'CONNECTIONS': 0
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Polygonize ...')
        UncleanedValleyBottom = Processing.runAlgorithm('gdalogr:polygonize', None,
                            {
                              'INPUT': SievedValleyBottomRaster.getOutputValue('OUTPUT'),
                              'FIELD': 'VALUE'
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Clean valley bottom ...')
        ValleyBottom = Processing.runAlgorithm('fluvialtoolbox:cleanvalleybottom', None,
                            {
                              'INPUT': UncleanedValleyBottom.getOutputValue('OUTPUT'),
                              'MIN_AREA': 50e4,
                              'MIN_HOLE_AREA': 10e4,
                              'FIELD': 'VALUE',
                              'VALUE': 1
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Simplify result ...')
        SimplifiedValleyBottom = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': ValleyBottom.getOutputValue('OUTPUT'),
                              'TOLERANCE': 10
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Smooth polygons ...')
        SmoothedValleyBottom = Processing.runAlgorithm('qgis:smoothgeometry', None,
                            {
                              'INPUT_LAYER': SimplifiedValleyBottom.getOutputValue('OUTPUT'),
                              'OUTPUT_LAYER': self.getOutputValue(self.OUTPUT_LAYER),
                              'ITERATIONS': 5,
                              'OFFSET': .25
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Done !')
