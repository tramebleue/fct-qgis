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

import gdal
import numpy as np

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

try:
    from ...lib.terrain_analysis import topo_stream_burn
    CYTHON = True
except ImportError:
    from ...lib.topo_stream_burn import topo_stream_burn
    CYTHON = False

class TopologicalStreamBurn(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Compute flow direction raster,
        using a variant of Wang and Liu fill sink algorithm
    """

    METADATA = AlgorithmMetadata.read(__file__, 'TopologicalStreamBurn')

    ELEVATIONS = 'ELEVATIONS'
    STREAMS = 'STREAMS'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.ELEVATIONS,
            self.tr('Elevations')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.STREAMS,
            self.tr('Rasterized Stream Network')))

        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Flow Direction')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        if CYTHON:
            feedback.pushInfo("Using Cython topo_stream_burn() ...")
        else:
            feedback.pushInfo("Pure python topo_stream_burn() - this may take a while ...")

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.ELEVATIONS, context)
        streams_lyr = self.parameterAsRasterLayer(parameters, self.STREAMS, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        elevations_ds = gdal.Open(elevations_lyr.dataProvider().dataSourceUri())
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()

        streams_ds = gdal.Open(streams_lyr.dataProvider().dataSourceUri())
        streams = streams_ds.GetRasterBand(1).ReadAsArray()

        geotransform = elevations_ds.GetGeoTransform()
        rx = geotransform[1]
        ry = -geotransform[5]

        out = topo_stream_burn(
            elevations,
            streams,
            nodata,
            rx,
            ry,
            minslope=1e-3,
            feedback=feedback)

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')
        # dst = driver.CreateCopy(output, flow_ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
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

        dst.GetRasterBand(1).WriteArray(np.asarray(out))
        dst.GetRasterBand(1).SetNoDataValue(-1)

        # Properly close GDAL resources
        elevations_ds = None
        streams_ds = None
        dst = None

        return {self.OUTPUT: output}
