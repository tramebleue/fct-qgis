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

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from .topo_stream_burn import topo_stream_burn
from ..metadata import AlgorithmMetadata

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

        driver = gdal.GetDriverByName('GTiff')
        dst = driver.CreateCopy(output, elevations_ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        # Properly close GDAL resources
        elevations_ds = None
        streams_ds = None
        dst = None

        return {self.OUTPUT: output}
