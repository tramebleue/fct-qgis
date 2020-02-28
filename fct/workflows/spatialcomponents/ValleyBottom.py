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

import processing
import os
import tempfile

from qgis.core import (
    QgsFeature,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum,
    QgsWkbTypes,
    QgsGeometry,
    QgsFeatureSink
)

from ..metadata import AlgorithmMetadata

class ValleyBottom(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ 
    Extract valley bottom over the studied area
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ValleyBottom')
    
    IN_DEM = 'IN_DEM'
    IN_STREAM = 'IN_STREAM'
    METHOD = 'METHOD'
    STEP = 'STEP'
    AGGREG = 'AGGREG'
    BUFFER = 'BUFFER'
    OUT_VB = 'OUT_VB'

    def initAlgorithm(self, configuration):

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.IN_DEM,
            self.tr('Input DEM'),
            [QgsProcessing.TypeRaster]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.IN_STREAM,
            self.tr('Input stream network'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD,
            self.tr('Detrending method'),
            allowMultiple=False,
            options=['Topological', 'Flow', 'Nearest'],
            defaultValue='Topological'))

        self.addParameter(QgsProcessingParameterNumber(
            self.STEP,
            self.tr('Disaggregation step'),
            defaultValue=50.0,
            minValue=1))

        self.addParameter(QgsProcessingParameterNumber(
            self.AGGREG,
            self.tr('Aggregation distance'),
            defaultValue=5.0,
            minValue=1))

        self.addParameter(QgsProcessingParameterNumber(
            self.BUFFER,
            self.tr('Large buffer size'),
            defaultValue=1500.0,
            minValue=1))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUT_VB,
            self.tr('Output valley bottom')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring
        
        # Step 1: Detrend DEM

        method = self.parameterAsString(parameters, self.METHOD, context)

        if method == '0':
            feedback.pushInfo(self.tr('Topological detrending...'))

            detrended_dem = processing.run('fct:detrenddem',
                {
                    'dem': self.parameterAsRasterLayer(parameters, self.IN_DEM, context),
                    'disaggregationdistance': self.parameterAsDouble(parameters, self.STEP, context), 
                    'fct:rasterdifference:Detrended': 'memory:', 
                    'stream': self.parameterAsVectorLayer(parameters, self.IN_STREAM, context)
                }, context=context)
            
            relative_dem = detrended_dem['fct:rasterdifference:Detrended']

        if method == '1':
            feedback.pushInfo(self.tr('Flow detrending...'))
            feedback.pushInfo(self.tr('  Flow direction...'))
            flow_dir = processing.run('fct:flowdirection',
                { 
                    'ELEVATIONS': self.parameterAsRasterLayer(parameters, self.IN_DEM, context), 
                    'OUTPUT': 'memory:' 
                }, context=context)

            feedback.pushInfo(self.tr('  Detrend DEM...'))
            detrended_dem = processing.run('fct:detrenddem',
                { 
                    'FLOW': flow_dir['OUTPUT'], 
                    'INPUT': self.parameterAsRasterLayer(parameters, self.IN_DEM, context), 
                    'OUTPUT': 'memory:', 
                    'STREAM': self.parameterAsVectorLayer(parameters, self.IN_STREAM, context)
                }, context=context)
            
            relative_dem = detrended_dem['OUTPUT']

        if method == '2':
            feedback.pushInfo(self.tr('Nearest detrending...'))

            detrended_dem = processing.run('fct:relativedem',
                {
                    'INPUT': self.parameterAsRasterLayer(parameters, self.IN_DEM, context),
                    'OUTPUT': 'memory:',
                    'STREAM': self.parameterAsVectorLayer(parameters, self.IN_STREAM, context)
                }, context=context)
            
            relative_dem = detrended_dem['OUTPUT']

        if feedback.isCanceled():
            return {}

        # Step 2: Compute and return Valley Bottom

        feedback.pushInfo(self.tr('Compute Valley Bottom...'))
        tmpdir = tempfile.mkdtemp(prefix='fct_')

        valleybottom = processing.run('fct:valleybottom',
            {
                'detrendeddem': relative_dem, 
                'gdal:sieve_1:VALLEYBOTTOM_RASTER': os.path.join(tmpdir, 'VB_RASTER.tif'),
                'inputstreamnetwork': self.parameterAsVectorLayer(parameters, self.IN_STREAM, context),
                'largebufferdistanceparameter': self.parameterAsDouble(parameters, self.BUFFER, context),
                'mergedistance': self.parameterAsDouble(parameters, self.AGGREG, context),
                'native:smoothgeometry_1:VALLEYBOTTOM_POLYGON': parameters['OUT_VB'],
                'thresholds': [-10,10,1]
            }, context=context, feedback=feedback)

        return {self.OUT_VB: valleybottom['native:smoothgeometry_1:VALLEYBOTTOM_POLYGON']}