# -*- coding: utf-8 -*-

"""
***************************************************************************
    ValleyBottom.py
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
from processing.core.outputs import OutputVector, OutputRaster
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
import gdal


class ValleyBottom(GeoAlgorithm):

    INPUT_DEM = 'INPUT_DEM'
    INPUT_NETWORK = 'INPUT_NETWORK'
    INPUT_ZOI = 'INPUT_ZOI'
    OUTPUT = 'OUTPUT'
    VALLEYBOTTOM_RASTER = 'VALLEYBOTTOM_RASTER'
    DISAGGREGATION_DISTANCE = 'DISAGGREGATION_DISTANCE'
    DISPLAY_INTERMEDIATE_RESULT = 'DISPLAY_INTERMEDIATE_RESULT'
    MERGE_DISTANCE = 'MERGE_DISTANCE'
    DO_CLEAN = 'DO_CLEAN'

    LARGE_BUFFER_DISTANCE_PARAM = 'LARGE_BUFFER_DISTANCE'
    SMALL_BUFFER_DISTANCE_PARAM = 'SMALL_BUFFER_DISTANCE'
    MIN_THRESHOLD_PARAM = 'MIN_THRESHOLD'
    MAX_THRESHOLD_PARAM = 'MAX_THRESHOLD'
    CLEAN_MIN_AREA_PARAM = 'CLEAN_MIN_AREA'
    CLEAN_MIN_HOLE_AREA_PARAM = 'CLEAN_MIN_HOLE_AREA'

    STEPS = 24

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Valley Bottom')
        self.group, self.i18n_group = self.trAlgorithm('Spatial Components')

        # Main parameters

        self.addParameter(ParameterRaster(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(ParameterVector(self.INPUT_NETWORK,
                                          self.tr('Input Stream Network'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_ZOI,
                                          self.tr('Zone of Interest'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterNumber(self.DISAGGREGATION_DISTANCE,
                                          self.tr('Disaggregation Step'), default=50.0, minValue=0.0))
        self.addParameter(ParameterNumber(self.MERGE_DISTANCE,
                                           self.tr('Merge polygons closer than distance'), default=50.0, minValue=0.0))
        self.addParameter(ParameterBoolean(self.DO_CLEAN,
                                           self.tr('Clean result layer ?'), True))

        self.addParameter(ParameterBoolean(self.DISPLAY_INTERMEDIATE_RESULT,
                                           self.tr('Display intermediate result layers ?'), False))

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

        self.addOutput(OutputRaster(self.VALLEYBOTTOM_RASTER, self.tr('Valley Bottom Raster')))

    def nextStep(self, description, progress):

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, description)
        progress.setText(description)
        progress.setPercentage(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1

    def processAlgorithm(self, progress):

        LARGE_BUFFER_DISTANCE = self.getParameterValue(self.LARGE_BUFFER_DISTANCE_PARAM)
        SMALL_BUFFER_DISTANCE = self.getParameterValue(self.SMALL_BUFFER_DISTANCE_PARAM)
        MIN_THRESHOLD = self.getParameterValue(self.MIN_THRESHOLD_PARAM)
        MAX_THRESHOLD = self.getParameterValue(self.MAX_THRESHOLD_PARAM)
        MIN_OBJECT_DISTANCE = self.getParameterValue(self.MERGE_DISTANCE)
        do_clean = self.getParameterValue(self.DO_CLEAN)
        CLEAN_MIN_AREA = self.getParameterValue(self.CLEAN_MIN_AREA_PARAM)
        CLEAN_MIN_HOLE_AREA = self.getParameterValue(self.CLEAN_MIN_HOLE_AREA_PARAM)
        display_result = self.getParameterValue(self.DISPLAY_INTERMEDIATE_RESULT)

        # Hard coded parameters
        SIMPLIFY_TOLERANCE = 25
        SPLIT_MAX_LENGTH = self.getParameterValue(self.DISAGGREGATION_DISTANCE)
        SIEVE_THRESHOLD = 40
        SMOOTH_ITERATIONS = 6
        SMOOTH_OFFSET = .15

        # Constants
        FOUR_CONNECTIVITY = 0
        LZW_COMPRESS = 3

        def handleResult(description):
            def _handle(alg, *args, **kw):
                if display_result:
                    for out in alg.outputs:
                        out.description = description
                    handleAlgorithmResults(alg, *args, **kw)
            return _handle

        self.current_step = 0
        
        self.nextStep('Clip stream network by ZOI ...', progress)
        ClippedNetwork = Processing.runAlgorithm('qgis:clip', None,
                            {
                              'INPUT': self.getParameterValue(self.INPUT_NETWORK),
                              'OVERLAY': self.getParameterValue(self.INPUT_ZOI)
                            })

        self.nextStep('Simplify network',progress)
        SimplifiedNetwork = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': ClippedNetwork.getOutputValue('OUTPUT'),
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })
        
        self.nextStep('Split network ...',progress)
        SplittedNetwork = Processing.runAlgorithm('fluvialtoolbox:splitlines', None,
                            {
                              'INPUT': SimplifiedNetwork.getOutputValue('OUTPUT'),
                              'MAXLENGTH': SPLIT_MAX_LENGTH
                            })

        self.nextStep('Extract points ...',progress)
        NetworkPoints = Processing.runAlgorithm('qgis:extractnodes', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT')
                            })
        
        self.nextStep('Compute large buffer ...',progress)
        LargeBuffer0 = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT'),
                              'DISTANCE': LARGE_BUFFER_DISTANCE,
                              'DISSOLVE': True
                            })

        LargeBuffer = Processing.runAlgorithm('qgis:clip', None, {
                              'INPUT': LargeBuffer0.getOutputValue('OUTPUT'),
                              'OVERLAY': self.getParameterValue(self.INPUT_ZOI)
                            })

        # self.nextStep('Clip large buffer ...',progress)
        # LargeBuffer = Processing.runAlgorithm('qgis:clip', None,
        #                     {
        #                       'INPUT': LargeBufferToClip.getOutputValue('OUTPUT'),
        #                       'OVERLAY': self.getParameterValue(self.INPUT_ZOI)
        #                     })
        
        self.nextStep('Compute small buffer ...',progress)
        SmallBuffer = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
                            {
                              'INPUT': SplittedNetwork.getOutputValue('OUTPUT'),
                              'DISTANCE': SMALL_BUFFER_DISTANCE,
                              'DISSOLVE': True
                            })

        self.nextStep('Compute thiessen polygons ...',progress)
        ThiessenPolygons = Processing.runAlgorithm('qgis:voronoipolygons', None,
                            {
                              'INPUT': NetworkPoints.getOutputValue('OUTPUT'),
                              'BUFFER': 10.0
                            })

        self.nextStep('Clip thiessen polygons ...',progress)
        ClippedThiessenPolygons = Processing.runAlgorithm('qgis:clip', None,
                            {
                              'INPUT': ThiessenPolygons.getOutputValue('OUTPUT'),
                              'OVERLAY': LargeBuffer.getOutputValue('OUTPUT')
                            })

        self.nextStep('Clip DEM ...',progress)
        ClippedDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', handleResult('Clipped DEM'),
                            {
                              'INPUT': self.getParameterValue(self.INPUT_DEM),
                              'MASK': LargeBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True
                            })

        self.nextStep('Extract minimum DEM ...',progress)
        MinDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', handleResult('Minimum DEM'),
                            {
                              'INPUT': ClippedDEM.getOutputValue('OUTPUT'),
                              'MASK': SmallBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': False,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True
                            })

        self.nextStep('Compute reference elevation for every polygon ...',progress)
        ReferencePolygons = Processing.runAlgorithm('qgis:zonalstatistics', handleResult('Reference polygons'),
                            {
                              'INPUT_RASTER': MinDEM.getOutputValue('OUTPUT'),
                              'RASTER_BAND': 1,
                              'INPUT_VECTOR': ClippedThiessenPolygons.getOutputValue('OUTPUT'),
                              'COLUMN_PREFIX': '_',
                              'GLOBAL_EXTENT': False
                            })

        layer = gdal.Open(ClippedDEM.getOutputValue('OUTPUT'))
        geotransform = layer.GetGeoTransform()
        pixel_width = geotransform[1]
        pixel_height = -geotransform[5]
        del layer

        self.nextStep('Convert to reference DEM ...',progress)
        ReferenceDEM0 = Processing.runAlgorithm('gdalogr:rasterize',  None,
                            {
                              'INPUT': ReferencePolygons.getOutputValue('OUTPUT_LAYER'),
                              'FIELD': '_min',
                              'TILED': True,
                              'COMPRESS': LZW_COMPRESS,
                              'DIMENSIONS': 1,
                              'WIDTH': pixel_width,
                              'HEIGHT': pixel_height,
                              'EXTRA': '-tap'
                            })

        ReferenceDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', handleResult('Clipped DEM'),
                            {
                              'INPUT': ReferenceDEM0.getOutputValue('OUTPUT'),
                              'MASK': LargeBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True
                            })

        self.nextStep('Compute relative DEM and extract bottom ...',progress)
        ValleyBottomRaster = Processing.runAlgorithm('fluvialtoolbox:differentialrasterthreshold', None,
                            {
                              'INPUT_DEM': ClippedDEM.getOutputValue('OUTPUT'),
                              'REFERENCE_DEM': ReferenceDEM.getOutputValue('OUTPUT'),
                              'MIN_THRESHOLD': MIN_THRESHOLD,
                              'MAX_THRESHOLD': MAX_THRESHOLD,
                            })

        # self.nextStep('Clip Raster Bottom ...',progress)
        # RawValleyBottomRaster = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', None,
        #                     {
        #                       'INPUT': ValleyBottomRasterToClip.getOutputValue('OUTPUT'),
        #                       'MASK': LargeBuffer.getOutputValue('OUTPUT'),
        #                       'ALPHA_BAND': False,
        #                       'CROP_TO_CUTLINE': True,
        #                       'KEEP_RESOLUTION': True,
        #                       'COMPRESS': LZW_COMPRESS,
        #                       'TILED': True
        #                     })

        self.setOutputValue(self.VALLEYBOTTOM_RASTER, ValleyBottomRaster.getOutputValue('OUTPUT'))

        if MIN_OBJECT_DISTANCE > 0:

          self.nextStep('Merge close objects...',progress)
          CleanedValleyBottomRaster = Processing.runAlgorithm('fluvialtoolbox:binaryclosing', handleResult('Binary Closing'),
                            {
                              'INPUT': ValleyBottomRaster.getOutputValue('OUTPUT'),
                              'DISTANCE': MIN_OBJECT_DISTANCE,
                              'ITERATIONS': 5
                            })
        else:

          self.nextStep('Sieve result ...',progress)
          CleanedValleyBottomRaster = Processing.runAlgorithm('gdalogr:sieve', None,
                            {
                              'INPUT': ValleyBottomRaster.getOutputValue('OUTPUT'),
                              'THRESHOLD': SIEVE_THRESHOLD,
                              'CONNECTIONS': FOUR_CONNECTIVITY
                            })

        # Polygonize Valley Bottom

        self.nextStep('Polygonize ...',progress)
        ValleyBottomPolygons = Processing.runAlgorithm('gdalogr:polygonize', handleResult('Uncleaned Valley Bottom'),
                            {
                              'INPUT': CleanedValleyBottomRaster.getOutputValue('OUTPUT'),
                              'FIELD': 'VALUE'
                            })

        # if MIN_OBJECT_DISTANCE > 0:

        #   self.nextStep('Simplify result ...',progress)
        #   MergedValleyBottom0 = Processing.runAlgorithm('qgis:simplifygeometries', None,
        #                         {
        #                           'INPUT': UncleanedValleyBottom.getOutputValue('OUTPUT'),
        #                           'TOLERANCE': SIMPLIFY_TOLERANCE
        #                         })

        #   self.nextStep('Merge close objects (step 1) ...',progress)
        #   MergedValleyBottom1 = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom0.getOutputValue('OUTPUT'),
        #                         'DISTANCE': MIN_OBJECT_DISTANCE,
        #                         'DISSOLVE': True
        #                       })

        #   self.nextStep('Merge close objects (step 2) ...',progress)
        #   MergedValleyBottom2 = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom1.getOutputValue('OUTPUT'),
        #                         'DISTANCE': -MIN_OBJECT_DISTANCE - (MIN_OBJECT_DISTANCE / 10),
        #                         'DISSOLVE': False
        #                       })

        #   self.nextStep('Merge close objects (step 3) ...',progress)
        #   MergedValleyBottom3 = Processing.runAlgorithm('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom2.getOutputValue('OUTPUT'),
        #                         'DISTANCE': (MIN_OBJECT_DISTANCE / 10),
        #                         'DISSOLVE': True
        #                       })

        #   UncleanedValleyBottom = MergedValleyBottom3


        # Clean result

        if self.getParameterValue(self.DO_CLEAN):

            self.nextStep('Remove small objects and parts ...',progress)
            CleanedValleyBottomPolygons = Processing.runAlgorithm('fluvialtoolbox:removesmallpolygonalobjects', None,
                                {
                                  'INPUT': ValleyBottomPolygons.getOutputValue('OUTPUT'),
                                  'MIN_AREA': CLEAN_MIN_AREA,
                                  'MIN_HOLE_AREA': CLEAN_MIN_HOLE_AREA,
                                  'FIELD': 'VALUE',
                                  'VALUE': 1
                                })

            self.nextStep('Simplify result ...',progress)
            SimplifiedValleyBottom = Processing.runAlgorithm('qgis:simplifygeometries', None,
                                {
                                  'INPUT': CleanedValleyBottomPolygons.getOutputValue('OUTPUT'),
                                  'TOLERANCE': SIMPLIFY_TOLERANCE
                                })

            self.nextStep('Smooth polygons ...',progress)
            SmoothedValleyBottom = Processing.runAlgorithm('qgis:smoothgeometry', None,
                                {
                                  'INPUT_LAYER': SimplifiedValleyBottom.getOutputValue('OUTPUT'),
                                  'OUTPUT_LAYER': self.getOutputValue(self.OUTPUT),
                                  'ITERATIONS': SMOOTH_ITERATIONS,
                                  'OFFSET': SMOOTH_OFFSET
                                })

        else:

            self.setOutputValue(self.OUTPUT, ValleyBottomPolygons.getOutputValue('OUTPUT'))

        self.nextStep('Done !',progress)
