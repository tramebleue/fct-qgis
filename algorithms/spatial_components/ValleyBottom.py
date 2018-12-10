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

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingOutputVectorLayer,
                       QgsProcessingOutputRasterLayer)

from processing.core.Processing import Processing
# from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
import gdal


class ValleyBottom(QgsProcessingAlgorithm):

    INPUT_DEM = 'INPUT_DEM'
    INPUT_NETWORK = 'INPUT_NETWORK'
    INPUT_ZOI = 'INPUT_ZOI'
    OUTPUT = 'OUTPUT'
    VALLEYBOTTOM_RASTER = 'VALLEYBOTTOM_RASTER'
    REFERENCE_DEM = 'REFERENCE_DEM'
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

    def name(self):
      return 'ValleyBottom'

    def groupId(self):
      return 'Spatial Components'

    def displayName(self):
      return self.tr(self.name())

    def group(self):
      return self.tr(self.groupId())

    def initAlgorithm(self, config):
        # Main parameters

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_NETWORK,
                                          self.tr('Input Stream Network'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT_ZOI,
                                          self.tr('Zone of Interest'), [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterNumber(self.DISAGGREGATION_DISTANCE,
                                          self.tr('Disaggregation Step'), defaultValue=50.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(self.MERGE_DISTANCE,
                                           self.tr('Merge polygons closer than distance'), defaultValue=50.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterBoolean(self.DO_CLEAN,
                                           self.tr('Clean result layer ?'), True))

        self.addParameter(QgsProcessingParameterBoolean(self.DISPLAY_INTERMEDIATE_RESULT,
                                           self.tr('Display intermediate result layers ?'), False))

        # Advanced parameters

        params = []
        params.append(QgsProcessingParameterNumber(self.LARGE_BUFFER_DISTANCE_PARAM,
                                      self.tr('Large buffer distance'), defaultValue=1000))
        params.append(QgsProcessingParameterNumber(self.SMALL_BUFFER_DISTANCE_PARAM,
                                      self.tr('Small buffer distance'), defaultValue=50))
        params.append(QgsProcessingParameterNumber(self.MIN_THRESHOLD_PARAM,
                                      self.tr('Bottom minimum relative elevation'), defaultValue=-10))
        params.append(QgsProcessingParameterNumber(self.MAX_THRESHOLD_PARAM,
                                      self.tr('Bottom maximum relative elevation'), defaultValue=10))
        params.append(QgsProcessingParameterNumber(self.CLEAN_MIN_AREA_PARAM,
                                      self.tr('Minimum object area'), defaultValue=50e4, minValue=0))
        params.append(QgsProcessingParameterNumber(self.CLEAN_MIN_HOLE_AREA_PARAM,
                                      self.tr('Minimum hole area'), defaultValue=10e4, minValue=0))

        for param in params:
            # TODO: update for new API
            # param.isAdvanced = True
            self.addParameter(param)

        # Output parameters
        
        self.addOutput(QgsProcessingOutputVectorLayer(self.OUTPUT, self.tr('Valley Bottom')))

        self.addOutput(QgsProcessingOutputRasterLayer(self.VALLEYBOTTOM_RASTER, self.tr('Valley Bottom Raster')))

        self.addOutput(QgsProcessingOutputRasterLayer(self.REFERENCE_DEM, self.tr('Reference DEM')))

    def nextStep(self, description, progress):

        # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, description)
        progress.setProgressText(description)
        # progress.setPercentage(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1

    def processAlgorithm(self, parameters, context, progress):

        LARGE_BUFFER_DISTANCE = self.parameterAsDouble(parameters, self.LARGE_BUFFER_DISTANCE_PARAM, context)
        SMALL_BUFFER_DISTANCE = self.parameterAsDouble(parameters, self.SMALL_BUFFER_DISTANCE_PARAM, context)
        MIN_THRESHOLD = self.parameterAsDouble(parameters, self.MIN_THRESHOLD_PARAM, context)
        MAX_THRESHOLD = self.parameterAsDouble(parameters, self.MAX_THRESHOLD_PARAM, context)
        MIN_OBJECT_DISTANCE = self.parameterAsDouble(parameters, self.MERGE_DISTANCE, context)
        SPLIT_MAX_LENGTH = self.parameterAsDouble(parameters, self.DISAGGREGATION_DISTANCE, context)

        CLEAN_MIN_AREA = self.parameterAsInt(parameters, self.CLEAN_MIN_AREA_PARAM, context)
        CLEAN_MIN_HOLE_AREA = self.parameterAsInt(parameters, self.CLEAN_MIN_HOLE_AREA_PARAM, context)

        do_clean = self.parameterAsBool(parameters, self.DO_CLEAN, context)
        display_result = self.parameterAsBool(parameters, self.DISPLAY_INTERMEDIATE_RESULT, context)

        # Hard coded parameters
        SIMPLIFY_TOLERANCE = 10
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
                              'INPUT': self.parameterAsVectorLayer(parameters, self.INPUT_NETWORK, context),
                              'OVERLAY': self.parameterAsVectorLayer(parameters, self.INPUT_ZOI, context)
                            })

        self.nextStep('Simplify network',progress)
        SimplifiedNetwork = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': ClippedNetwork.getOutputValue('OUTPUT'),
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })
        
        self.nextStep('Split network ...',progress)
        SplittedNetwork = Processing.runAlgorithm('fluvialcorridortoolbox:splitlines', None,
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
                              'OVERLAY': self.parameterAsVectorLayer(parameters, self.INPUT_ZOI, context)
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
                              'INPUT': self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context),
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

        ReferenceDEM = Processing.runAlgorithm('gdalogr:cliprasterbymasklayer', None,
                            {
                              'INPUT': ReferenceDEM0.getOutputValue('OUTPUT'),
                              'MASK': LargeBuffer.getOutputValue('OUTPUT'),
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True,
                              'OUTPUT': self.getOutputValue(self.REFERENCE_DEM)
                            })

        self.nextStep('Compute relative DEM and extract bottom ...',progress)
        ValleyBottomRaster = Processing.runAlgorithm('fluvialcorridortoolbox:differentialrasterthreshold', None,
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
          CleanedValleyBottomRaster = Processing.runAlgorithm('fluvialcorridortoolbox:binaryclosing', handleResult('Binary Closing'),
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
            CleanedValleyBottomPolygons = Processing.runAlgorithm('fluvialcorridortoolbox:removesmallpolygonalobjects', None,
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


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
      return ValleyBottom()
