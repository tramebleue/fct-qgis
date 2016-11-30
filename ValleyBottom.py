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
from processing.core.parameters import ParameterBoolean
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
import gdal


class ValleyBottom(GeoAlgorithm):

    INPUT_DEM = 'INPUT_DEM'
    INPUT_NETWORK = 'INPUT_NETWORK'
    INPUT_ZOI = 'INPUT_ZOI'
    OUTPUT = 'OUTPUT'
    DISPLAY_INTERMEDIATE_RESULT = 'DISPLAY_INTERMEDIATE_RESULT'
    DO_CLEAN = 'DO_CLEAN'

    LARGE_BUFFER_DISTANCE_PARAM = 'LARGE_BUFFER_DISTANCE'
    SMALL_BUFFER_DISTANCE_PARAM = 'SMALL_BUFFER_DISTANCE'
    MIN_THRESHOLD_PARAM = 'MIN_THRESHOLD'
    MAX_THRESHOLD_PARAM = 'MAX_THRESHOLD'
    CLEAN_MIN_AREA_PARAM = 'CLEAN_MIN_AREA'
    CLEAN_MIN_HOLE_AREA_PARAM = 'CLEAN_MIN_HOLE_AREA'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Valley Bottom')
        self.group, self.i18n_group = self.trAlgorithm('Main')

        # Main parameters

        self.addParameter(ParameterRaster(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(ParameterVector(self.INPUT_NETWORK,
                                          self.tr('Input Stream Network'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_ZOI,
                                          self.tr('Zone of Interest'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterBoolean(self.DISPLAY_INTERMEDIATE_RESULT,
                                           self.tr('Display intermediate result layers ?'), True))
        self.addParameter(ParameterBoolean(self.DO_CLEAN,
                                           self.tr('Clean result layer ?'), True))

        # Advanced parameters

        params = []
        params.append(ParameterNumber(self.LARGE_BUFFER_DISTANCE_PARAM,
                                      self.tr('Large buffer distance'), default=1000))
        params.append(ParameterNumber(self.SMALL_BUFFER_DISTANCE_PARAM,
                                      self.tr('Small buffer distance'), default=50))
        params.append(ParameterNumber(self.MIN_THRESHOLD_PARAM,
                                      self.tr('Bottom minimum relative elevation'), default=-10))
        params.append(ParameterNumber(self.MAX_THRESHOLD_PARAM,
                                      self.tr('Bottom maximum relative elevation'), default=10))
        params.append(ParameterNumber(self.CLEAN_MIN_AREA_PARAM,
                                      self.tr('Minimum object area'), default=50e4, minValue=0))
        params.append(ParameterNumber(self.CLEAN_MIN_HOLE_AREA_PARAM,
                                      self.tr('Minimum hole area'), default=10e4, minValue=0))

        for param in params:
            param.isAdvanced = True
            self.addParameter(param)
        
        self.addOutput(OutputVector(self.OUTPUT, self.tr('Valley Bottom')))

    def processAlgorithm(self, progress):

        LARGE_BUFFER_DISTANCE = self.getParameterValue(self.LARGE_BUFFER_DISTANCE_PARAM)
        SMALL_BUFFER_DISTANCE = self.getParameterValue(self.SMALL_BUFFER_DISTANCE_PARAM)
        MIN_THRESHOLD = self.getParameterValue(self.MIN_THRESHOLD_PARAM)
        MAX_THRESHOLD = self.getParameterValue(self.MAX_THRESHOLD_PARAM)
        CLEAN_MIN_AREA = self.getParameterValue(self.CLEAN_MIN_AREA_PARAM)
        CLEAN_MIN_HOLE_AREA = self.getParameterValue(self.CLEAN_MIN_HOLE_AREA_PARAM)
        display_result = self.getParameterValue(self.DISPLAY_INTERMEDIATE_RESULT)

        # Hard coded parameters
        SIMPLIFY_TOLERANCE = 20
        SPLIT_MAX_LENGTH = 50
        SIEVE_THRESHOLD = 40
        SMOOTH_ITERATIONS = 5
        SMOOTH_OFFSET = .25

        # Constants
        FOUR_CONNECTIVITY = 0
        LZW_COMPRESS = 3

        def handleResult(*args, **kw):
            if display_result:
                handleAlgorithmResults(*args, **kw)

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
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })
        current = current + 1
        progress.setPercentage(int(current * total))
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Split network ...')
        SplittedNetwork = Processing.runAlgorithm('fluvialtoolbox:splitlinestring', None,
                            {
                              'INPUT': SimplifiedNetwork.getOutputValue('OUTPUT'),
                              'MAXLENGTH': SPLIT_MAX_LENGTH
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
                              'DISTANCE': LARGE_BUFFER_DISTANCE,
                              'DISSOLVE': True
                            })
        current = current + 1
        progress.setPercentage(int(current * total))
        
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute small buffer ...')
        SmallBuffer = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT'),
                              'DISTANCE': SMALL_BUFFER_DISTANCE,
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
                              'COMPRESS': LZW_COMPRESS,
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
                              'COMPRESS': LZW_COMPRESS,
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

        layer = gdal.Open(self.getParameterValue(self.INPUT_DEM))
        geotransform = layer.GetGeoTransform()
        pixel_width = geotransform[1]
        pixel_height = -geotransform[5]
        del layer

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Convert to reference DEM ...')
        ReferenceDEM = Processing.runAlgorithm('gdalogr:rasterize', None,
                            {
                              'INPUT': ReferencePolygons.getOutputValue('OUTPUT_LAYER'),
                              'FIELD': '_median',
                              'TILED': True,
                              'COMPRESS': LZW_COMPRESS,
                              'DIMENSIONS': 1,
                              'WIDTH': pixel_width,
                              'HEIGHT': pixel_height,
                              'EXTRA': '-tap'
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Compute relative DEM and extract bottom ...')
        ValleyBottomRaster = Processing.runAlgorithm('fluvialtoolbox:differentialrasterthreshold', handleResult,
                            {
                              'INPUT_DEM': ClippedDEM.getOutputValue('OUTPUT'),
                              'REFERENCE_DEM': ReferenceDEM.getOutputValue('OUTPUT'),
                              'MIN_THRESHOLD': MIN_THRESHOLD,
                              'MAX_THRESHOLD': MAX_THRESHOLD,
                            })
        current = current + 1
        progress.setPercentage(int(current * total))


        # Polygonize Valley Bottom

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Sieve result ...')
        SievedValleyBottomRaster = Processing.runAlgorithm('gdalogr:sieve', None,
                            {
                              'INPUT': ValleyBottomRaster.getOutputValue('OUTPUT'),
                              'THRESHOLD': SIEVE_THRESHOLD,
                              'CONNECTIONS': FOUR_CONNECTIVITY
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Polygonize ...')
        UncleanedValleyBottom = Processing.runAlgorithm('gdalogr:polygonize', handleResult,
                            {
                              'INPUT': SievedValleyBottomRaster.getOutputValue('OUTPUT'),
                              'FIELD': 'VALUE'
                            })
        current = current + 1
        progress.setPercentage(int(current * total))

        # Clean result

        if self.getParameterValue(self.DO_CLEAN):

            ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Remove small objects and parts ...')
            ValleyBottom = Processing.runAlgorithm('fluvialtoolbox:removesmallpolygonalobjects', None,
                                {
                                  'INPUT': UncleanedValleyBottom.getOutputValue('OUTPUT'),
                                  'MIN_AREA': CLEAN_MIN_AREA,
                                  'MIN_HOLE_AREA': CLEAN_MIN_HOLE_AREA,
                                  'FIELD': 'VALUE',
                                  'VALUE': 1
                                })
            current = current + 1
            progress.setPercentage(int(current * total))

            ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Simplify result ...')
            SimplifiedValleyBottom = Processing.runAlgorithm('qgis:simplifygeometries', None,
                                {
                                  'INPUT': ValleyBottom.getOutputValue('OUTPUT'),
                                  'TOLERANCE': SIMPLIFY_TOLERANCE
                                })
            current = current + 1
            progress.setPercentage(int(current * total))

            ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Smooth polygons ...')
            SmoothedValleyBottom = Processing.runAlgorithm('qgis:smoothgeometry', None,
                                {
                                  'INPUT_LAYER': SimplifiedValleyBottom.getOutputValue('OUTPUT'),
                                  'OUTPUT_LAYER': self.getOutputValue(self.OUTPUT),
                                  'ITERATIONS': SMOOTH_ITERATIONS,
                                  'OFFSET': SMOOTH_OFFSET
                                })
            current = current + 1
            progress.setPercentage(int(current * total))

        else:

            self.setOutputValue(self.OUTPUT, UncleanedValleyBottom.getOutputValue('OUTPUT'))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Done !')
