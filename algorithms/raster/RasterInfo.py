# -*- coding: utf-8 -*-

"""
RasterInfo

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
    QgsProcessingParameterRasterLayer,
    QgsProcessingOutputNumber
)

from ..metadata import AlgorithmMetadata

class RasterInfo(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Return horizontal and vertical resolution of input raster
    """

    METADATA = AlgorithmMetadata.read(__file__, 'RasterInfo')

    INPUT = 'INPUT'
    XRES = 'XRES'
    YRES = 'YRES'
    XSIZE = 'XSIZE'
    YSIZE = 'YSIZE'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Input Raster')))

        self.addOutput(QgsProcessingOutputNumber(self.XRES, self.tr('Horizontal Resolution')))

        self.addOutput(QgsProcessingOutputNumber(self.YRES, self.tr('Vertical Resolution')))

        self.addOutput(QgsProcessingOutputNumber(self.XSIZE, self.tr('Width (Pixels)')))

        self.addOutput(QgsProcessingOutputNumber(self.YSIZE, self.tr('Height (Pixels)')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        dem = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        path = str(dem.dataProvider().dataSourceUri())

        raster = gdal.Open(path)
        geotransform = raster.GetGeoTransform()
        xres = geotransform[1]
        yres = -geotransform[5]
        xsize = raster.RasterXSize
        ysize = raster.RasterYSize


        return {
            self.XRES: xres,
            self.YRES: yres,
            self.XSIZE: xsize,
            self.YSIZE: ysize
        }
