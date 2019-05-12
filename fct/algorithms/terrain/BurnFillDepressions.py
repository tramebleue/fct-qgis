# -*- coding: utf-8 -*-

"""
TopologicalStreamBurn

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from osgeo import gdal
import numpy as np

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

class BurnFillDepressions(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute flow direction raster,
    using a variant of Wang and Liu priority flood algorithm
    that processes stream cell in before other cells.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'BurnFillDepressions')

    ELEVATIONS = 'ELEVATIONS'
    STREAMS = 'STREAMS'
    ZDELTA = 'ZDELTA'
    OUTPUT = 'OUTPUT'
    BURNED = 'BURNED'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.ELEVATIONS,
            self.tr('Elevations')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.STREAMS,
            self.tr('Rasterized Stream Network')))

        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addParameter(QgsProcessingParameterNumber(
            self.ZDELTA,
            self.tr('Minimum Z Delta Between Cells'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0,
            defaultValue=0.0005))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.BURNED,
            self.tr('Burned DEM'),
            optional=True))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import topo_stream_burn
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from ...lib.terrain_analysis import topo_stream_burn

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.ELEVATIONS, context)
        streams_lyr = self.parameterAsRasterLayer(parameters, self.STREAMS, context)
        zdelta = self.parameterAsDouble(parameters, self.ZDELTA, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        burned = self.parameterAsOutputLayer(parameters, self.BURNED, context)

        elevations_ds = gdal.Open(elevations_lyr.dataProvider().dataSourceUri())
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()

        streams_ds = gdal.Open(streams_lyr.dataProvider().dataSourceUri())
        streams = streams_ds.GetRasterBand(1).ReadAsArray()

        # geotransform = elevations_ds.GetGeoTransform()
        # rx = geotransform[1]
        # ry = -geotransform[5]

        flow = topo_stream_burn(
            elevations,
            streams,
            nodata,
            zdelta,
            feedback=feedback)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write flow direction ...'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=elevations_ds.RasterXSize,
            ysize=elevations_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Int16,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(elevations_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(elevations_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(flow)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        # Properly close GDAL resources
        dst = None

        if burned:

            feedback.pushInfo(self.tr('Write burned elevations ...'))

            dst = driver.Create(
                burned,
                xsize=elevations_ds.RasterXSize,
                ysize=elevations_ds.RasterYSize,
                bands=1,
                eType=gdal.GDT_Float32,
                options=['TILED=YES', 'COMPRESS=DEFLATE'])
            dst.SetGeoTransform(elevations_ds.GetGeoTransform())
            # dst.SetProjection(srs.exportToWkt())
            dst.SetProjection(elevations_lyr.crs().toWkt())

            dst.GetRasterBand(1).WriteArray(elevations)
            dst.GetRasterBand(1).SetNoDataValue(nodata)

            # Properly close GDAL resources
            dst = None

        # Properly close GDAL resources
        elevations_ds = None
        streams_ds = None

        return {
            self.OUTPUT: output,
            self.BURNED: burned
        }
