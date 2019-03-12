# -*- coding: utf-8 -*-

"""
ValleyBottom

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import os

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingModelAlgorithm
)

from ..metadata import AlgorithmMetadata

class ValleyBottom(AlgorithmMetadata, QgsProcessingModelAlgorithm):
    """ Extract Valley Bottom from relative DEM
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.METADATA = AlgorithmMetadata.read(__file__, type(self).__name__)
        self.fromFile(os.path.join(os.path.dirname(__file__), type(self).__name__ + '.model3'))


# OLD VERSION OF VALLEYBOTTOM BELOW
'''
from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterRasterDestination)

# from processing.core.Processing import Processing
# from processing.core.ProcessingLog import ProcessingLog
# from processing.gui.Postprocessing import handleAlgorithmResults
import tempfile
import os
import processing
import gdal

from ..metadata import AlgorithmMetadata

class ValleyBottom(AlgorithmMetadata, QgsProcessingAlgorithm):

    METADATA = AlgorithmMetadata.read(__file__, 'ValleyBottom')

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

    def initAlgorithm(self, config=None):
        # Main parameters

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_NETWORK,
                                          self.tr('Input Stream Network'), [QgsProcessing.TypeVectorLine]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_ZOI,
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
        
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT, self.tr('Valley Bottom')))

        self.addParameter(QgsProcessingParameterRasterDestination(self.VALLEYBOTTOM_RASTER, self.tr('Valley Bottom Raster')))

        self.addParameter(QgsProcessingParameterRasterDestination(self.REFERENCE_DEM, self.tr('Reference DEM')))

    def nextStep(self, description, feedback):
        feedback.pushInfo(description)
        feedback.setProgress(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1

    def processAlgorithm(self, parameters, context, feedback):

        # Value parameters
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

        # Layer parameters
        INPUT_NETWORK_LAYER = self.parameterAsVectorLayer(parameters, self.INPUT_NETWORK, context)
        INPUT_DEM_LAYER = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        INPUT_ZOI_LAYER = self.parameterAsVectorLayer(parameters, self.INPUT_ZOI, context)

        REFERENCE_DEM_LAYER = self.parameterAsOutputLayer(parameters, self.REFERENCE_DEM, context)

        # Hard coded parameters
        SIMPLIFY_TOLERANCE = 10
        SIEVE_THRESHOLD = 40
        SMOOTH_ITERATIONS = 6
        SMOOTH_OFFSET = .15

        # Constants
        FOUR_CONNECTIVITY = 0
        LZW_COMPRESS = 3

        # Create temp dir for temp rasters
        tmpdir = tempfile.mkdtemp(prefix='fct_')

        # def handleResult(description):
        #     def _handle(alg, *args, **kw):
        #         if display_result:
        #             for out in alg.outputs:
        #                 out.description = description
        #             handleAlgorithmResults(alg, *args, **kw)
        #     return _handle

        self.current_step = 0
        
        # TODO: add native:mergelines to merge multi-parts polylines
        
        self.nextStep('Clip stream network by ZOI ...', feedback)
        ClippedNetwork = processing.run('qgis:clip',
                            {
                              'INPUT': INPUT_NETWORK_LAYER,
                              'OVERLAY': INPUT_ZOI_LAYER,
                              'OUTPUT': 'memory:'
                            }, context=context)

        self.nextStep('Simplify network',feedback)
        SimplifiedNetwork = processing.run('qgis:simplifygeometries',
                            {
                              'INPUT': ClippedNetwork['OUTPUT'],
                              'METHOD': 0,
                              'TOLERANCE': SIMPLIFY_TOLERANCE,
                              'OUTPUT': 'memory:'
                            }, context=context)
        
        self.nextStep('Split network ...',feedback)
        NetworkPoints = processing.run('qgis:pointsalonglines',
                            {
                              'INPUT': SimplifiedNetwork['OUTPUT'],
                              'DISTANCE': SPLIT_MAX_LENGTH,
                              'OUTPUT': 'memory:'
                            }, context=context)

        # self.nextStep('Split network ...',feedback)
        # SplittedNetwork = processing.run('fluvialcorridortoolbox:splitlines',
        #                     {
        #                       'INPUT': SimplifiedNetwork['OUTPUT'],
        #                       'MAXLENGTH': SPLIT_MAX_LENGTH,
        #                       'OUTPUT': 'memory:'
        #                     })

        # self.nextStep('Extract points ...',feedback)
        # NetworkPoints = processing.run('qgis:extractnodes',
        #                     {
        #                       'INPUT': SplittedNetwork['OUTPUT'],
        #                       'OUTPUT': 'memory:'
        #                     })
        
        self.nextStep('Compute large buffer ...',feedback)
        LargeBuffer0 = processing.run('qgis:buffer',
                            {
                              'INPUT': SimplifiedNetwork['OUTPUT'],
                              'DISTANCE': LARGE_BUFFER_DISTANCE,
                              'DISSOLVE': True,
                              'OUTPUT': 'memory:'
                            }, context=context)

        LargeBuffer = processing.run('qgis:clip', 
                            {
                              'INPUT': LargeBuffer0['OUTPUT'],
                              'OVERLAY': INPUT_ZOI_LAYER,
                              'OUTPUT': 'memory:'
                            }, context=context)

        # self.nextStep('Clip large buffer ...',feedback)
        # LargeBuffer = processing.run('qgis:clip', None,
        #                     {
        #                       'INPUT': LargeBufferToClip['OUTPUT'],
        #                       'OVERLAY': self.getParameterValue(self.INPUT_ZOI)
        #                     })
        
        self.nextStep('Compute small buffer ...',feedback)
        SmallBuffer = processing.run('qgis:buffer',
                            {
                              'INPUT': SimplifiedNetwork['OUTPUT'],
                              'DISTANCE': SMALL_BUFFER_DISTANCE,
                              'DISSOLVE': True,
                              'OUTPUT': 'memory:'
                            }, context=context)

        self.nextStep('Compute thiessen polygons ...',feedback)
        ThiessenPolygons = processing.run('qgis:voronoipolygons',
                            {
                              'INPUT': NetworkPoints['OUTPUT'],
                              'BUFFER': 10.0,
                              'OUTPUT': 'memory:'
                            }, context=context)

        self.nextStep('Clip thiessen polygons ...',feedback)
        ClippedThiessenPolygons = processing.run('qgis:clip',
                            {
                              'INPUT': ThiessenPolygons['OUTPUT'],
                              'OVERLAY': LargeBuffer['OUTPUT'],
                              'OUTPUT': 'memory:'
                            }, context=context)

        self.nextStep('Clip DEM ...',feedback)
        CLIPPED_DEM = os.path.join(tmpdir, 'CLIPPED_DEM.TIF')
        # TODO: load this result in gqis interface if option checked only
        ClippedDEM = processing.run('gdal:cliprasterbymasklayer',
                            {
                              'INPUT': INPUT_DEM_LAYER,
                              'MASK': LargeBuffer['OUTPUT'],
                              'ALPHA_BAND': False,
                              'NODATA': 9999,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True,
                              'OUTPUT': CLIPPED_DEM
                            }, context=context)

        self.nextStep('Extract minimum DEM ...',feedback)
        MIN_DEM = os.path.join(tmpdir, 'MIN_DEM.TIF')
        # TODO: load this result in gqis interface if option checked only
        MinDEM = processing.run('gdal:cliprasterbymasklayer',
                            {
                              'INPUT': CLIPPED_DEM,
                              'MASK': SmallBuffer['OUTPUT'],
                              'NODATA': 9999,
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': False,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True,
                              'OUTPUT': MIN_DEM
                            }, context=context)

        self.nextStep('Compute reference elevation for every polygon ...',feedback)
        # TODO: load this result in gqis interface if option checked only
        ReferencePolygons = processing.run('qgis:zonalstatistics',
                            {
                              'INPUT_RASTER': MIN_DEM,
                              'RASTER_BAND': 1,
                              'INPUT_VECTOR': ClippedThiessenPolygons['OUTPUT'],
                              'COLUMN_PREFIX': '_',
                              'STATS': 5
                            }, context=context)
        

        layer = gdal.Open(CLIPPED_DEM)
        geotransform = layer.GetGeoTransform()
        pixel_width = geotransform[1]
        pixel_height = -geotransform[5]
        del layer

        self.nextStep('Convert to reference DEM ...',feedback)
        REFERENCE_DEM0 = os.path.join(tmpdir, 'REFERENCE_DEM0.TIF')
        ReferenceDEM0 = processing.run('gdal:rasterize',
                            {
                              'INPUT': ReferencePolygons['INPUT_VECTOR'],
                              'FIELD': '_min',
                              'TILED': True,
                              'COMPRESS': LZW_COMPRESS,
                              'NODATA': 9999,
                              'UNITS': 1,
                              'WIDTH': pixel_width,
                              'HEIGHT': pixel_height,
                              'EXTENT': CLIPPED_DEM,
                              'OPTIONS': '-tap',
                              'OUTPUT': REFERENCE_DEM0
                            }, context=context)

        ReferenceDEM = processing.run('gdal:cliprasterbymasklayer',
                            {
                              'INPUT': REFERENCE_DEM0,
                              'MASK': LargeBuffer['OUTPUT'],
                              'NODATA': 9999,
                              'ALPHA_BAND': False,
                              'CROP_TO_CUTLINE': True,
                              'KEEP_RESOLUTION': True,
                              'COMPRESS': LZW_COMPRESS,
                              'TILED': True,
                              'OUTPUT': REFERENCE_DEM_LAYER
                            }, context=context)

        self.nextStep('Compute relative DEM and extract bottom ...',feedback)
        VB_RASTER = os.path.join(tmpdir, 'VB_RASTER.TIF')
        ValleyBottomRaster = processing.run('fct:DifferentialRasterThreshold',
                            {
                              'INPUT_DEM': CLIPPED_DEM,
                              'REFERENCE_DEM': ReferenceDEM['OUTPUT'],
                              'MIN_THRESHOLD': MIN_THRESHOLD,
                              'MAX_THRESHOLD': MAX_THRESHOLD,
                              'OUTPUT': VB_RASTER
                            }, context=context)

        # self.nextStep('Clip Raster Bottom ...',feedback)
        # RawValleyBottomRaster = processing.run('gdal:cliprasterbymasklayer', None,
        #                     {
        #                       'INPUT': ValleyBottomRasterToClip['OUTPUT'],
        #                       'MASK': LargeBuffer['OUTPUT'],
        #                       'ALPHA_BAND': False,
        #                       'CROP_TO_CUTLINE': True,
        #                       'KEEP_RESOLUTION': True,
        #                       'COMPRESS': LZW_COMPRESS,
        #                       'TILED': True
        #                     })

        if MIN_OBJECT_DISTANCE > 0:
          
          # TODO: deal with nodata before the binary closing
          self.nextStep('Merge close objects...',feedback)
          CLEAN_VB = os.path.join(tmpdir, 'CLEAN_VB.TIF')
          CleanedValleyBottomRaster = processing.run('fct:BinaryClosing',
                            {
                              'INPUT': ValleyBottomRaster['OUTPUT'],
                              'BAND': 1,
                              'DISTANCE': MIN_OBJECT_DISTANCE,
                              'ITERATIONS': 5,
                              'OUTPUT': CLEAN_VB
                            }, context=context)
        else:

          self.nextStep('Sieve result ...',feedback)
          CLEANED_VB = os.path.join(tmpdir, 'CLEANED_VB.TIF')
          CleanedValleyBottomRaster = processing.run('gdal:sieve',
                            {
                              'INPUT': ValleyBottomRaster['OUTPUT'],
                              'THRESHOLD': SIEVE_THRESHOLD,
                              'CONNECTIONS': FOUR_CONNECTIVITY,
                              'OUTPUT': CLEANED_VB
                            }, context=context)

        # Polygonize Valley Bottom

        self.nextStep('Polygonize ...',feedback)
        # TODO: load this result in gqis interface if option checked only
        VB_POLYGONS = os.path.join(tmpdir, 'VB_POLYGONS.SHP')
        ValleyBottomPolygons = processing.run('gdal:polygonize',
                            {
                              'INPUT': CleanedValleyBottomRaster['OUTPUT'],
                              'BAND': 1,
                              'FIELD': 'VALUE',
                              'OUTPUT': VB_POLYGONS
                            }, context=context)

        # if MIN_OBJECT_DISTANCE > 0:

        #   self.nextStep('Simplify result ...',feedback)
        #   MergedValleyBottom0 = processing.run('qgis:simplifygeometries', None,
        #                         {
        #                           'INPUT': UncleanedValleyBottom['OUTPUT'],
        #                           'TOLERANCE': SIMPLIFY_TOLERANCE
        #                         })

        #   self.nextStep('Merge close objects (step 1) ...',feedback)
        #   MergedValleyBottom1 = processing.run('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom0['OUTPUT'],
        #                         'DISTANCE': MIN_OBJECT_DISTANCE,
        #                         'DISSOLVE': True
        #                       })

        #   self.nextStep('Merge close objects (step 2) ...',feedback)
        #   MergedValleyBottom2 = processing.run('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom1['OUTPUT'],
        #                         'DISTANCE': -MIN_OBJECT_DISTANCE - (MIN_OBJECT_DISTANCE / 10),
        #                         'DISSOLVE': False
        #                       })

        #   self.nextStep('Merge close objects (step 3) ...',feedback)
        #   MergedValleyBottom3 = processing.run('qgis:fixeddistancebuffer', None,
        #                       {
        #                         'INPUT': MergedValleyBottom2['OUTPUT'],
        #                         'DISTANCE': (MIN_OBJECT_DISTANCE / 10),
        #                         'DISSOLVE': True
        #                       })

        #   UncleanedValleyBottom = MergedValleyBottom3


        # Clean result

        if self.parameterAsBool(parameters, self.DO_CLEAN, context):

            self.nextStep('Remove small objects and parts ...',feedback)
            CLEAN_VB_POLYGONS = os.path.join(tmpdir, 'CLEAN_VB_POLYGONS.TIF')
            CleanedValleyBottomPolygons = processing.run('fct:RemoveSmallPolygonalObjects',
                                {
                                  'INPUT': ValleyBottomPolygons['OUTPUT'],
                                  'MIN_AREA': CLEAN_MIN_AREA,
                                  'MIN_HOLE_AREA': CLEAN_MIN_HOLE_AREA,
                                  'FIELD': 'VALUE',
                                  'VALUE': 1,
                                  'OUTPUT': CLEAN_VB_POLYGONS
                                }, context=context)

            self.nextStep('Simplify result ...',feedback)
            SimplifiedValleyBottom = processing.run('qgis:simplifygeometries',
                                {
                                  'INPUT': CleanedValleyBottomPolygons['OUTPUT'],
                                  'TOLERANCE': SIMPLIFY_TOLERANCE,
                                  'OUTPUT': 'memory:'
                                }, context=context)

            self.nextStep('Smooth polygons ...',feedback)
            SmoothedValleyBottom = processing.run('qgis:smoothgeometry',
                                {
                                  'INPUT_LAYER': SimplifiedValleyBottom['OUTPUT'],
                                  'OUTPUT_LAYER': self.getOutputValue(self.OUTPUT),
                                  'ITERATIONS': SMOOTH_ITERATIONS,
                                  'OFFSET': SMOOTH_OFFSET,
                                  'OUTPUT': 'memory:'
                                }, context=context)
            
            VALLEYBOTTOM_POLYGON = SmoothedValleyBottom['OUTPUT']

        else:

            VALLEYBOTTOM_POLYGON = ValleyBottomPolygons['OUTPUT']

        self.nextStep('Done !',feedback)


        return {self.VALLEYBOTTOM_RASTER: ValleyBottomRaster['OUTPUT'],
                self.REFERENCE_DEM: ReferenceDEM['OUTPUT'],
                self.OUTPUT: VALLEYBOTTOM_POLYGON}


    def tr(self, string):
        return QCoreApplication.translate('FluvialCorridorToolbox', string)

    def createInstance(self):
      return ValleyBottom()
'''