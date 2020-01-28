# -*- coding: utf-8 -*-

"""
FlowAccumulation

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import numpy as np
from osgeo import gdal
# import osr

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

class StreamFlowDirection(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute D8 Flow Direction from Digital Elevation Model
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StreamFlowDirection')

    ELEVATIONS = 'ELEVATIONS'
    STREAMS = 'STREAMS'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.ELEVATIONS,
            self.tr('Digital Elevation Model')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.STREAMS,
            self.tr('Rasterized Stream Network')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Flow Direction')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import stream_flow
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from ...lib.terrain_analysis import stream_flow

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.ELEVATIONS, context)
        streams_lyr = self.parameterAsRasterLayer(parameters, self.STREAMS, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        driver = gdal.GetDriverByName('GTiff')

        elevations_ds = gdal.Open(elevations_lyr.dataProvider().dataSourceUri())
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()

        streams_ds = gdal.Open(streams_lyr.dataProvider().dataSourceUri())
        streams = streams_ds.GetRasterBand(1).ReadAsArray()

        flow = stream_flow(elevations, streams, nodata, feedback=feedback)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(50)
        feedback.pushInfo(self.tr('Write output ...'))

        dst = driver.Create(
            output,
            xsize=elevations_ds.RasterXSize,
            ysize=elevations_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Int16,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])

        dst.SetGeoTransform(elevations_ds.GetGeoTransform())
        dst.SetProjection(elevations_lyr.crs().toWkt())
        dst.GetRasterBand(1).WriteArray(flow)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        feedback.setProgress(100)

        # Properly close GDAL resources
        elevations_ds = None
        streams_ds = None
        dst = None

        return {self.OUTPUT: output}
