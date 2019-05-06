# -*- coding: utf-8 -*-

"""
Simple Raster Filters

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

from enum import IntEnum
from osgeo import gdal

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from processing.algs.gdal.GdalUtils import GdalUtils # pylint:disable=import-error
from ..metadata import AlgorithmMetadata

class SimpleRasterFilterType(IntEnum):
    """
    Anisotropic Diffusion (Perona-Malik) Filter 
    """

    MEAN_FILTER = 0
    MEDIAN_FILTER = 1
    MIN_FILTER = 2
    MAX_FILTER = 3

class SimpleRasterFilter(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Apply simple image filter to raster.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SimpleRasterFilter')

    INPUT = 'INPUT'
    BANDS = 'BANDS'
    FILTER_TYPE = 'FILTER_TYPE'
    SIZE = 'SIZE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Input Raster')))

        self.addParameter(QgsProcessingParameterBand(
            self.BANDS,
            self.tr('Bands To Process'),
            parentLayerParameterName=self.INPUT,
            allowMultiple=True,
            defaultValue=[1]))

        self.addParameter(QgsProcessingParameterEnum(
            self.FILTER_TYPE,
            self.tr('Filter Type'),
            options=map(self.tr, [
                'Mean',
                'Median',
                'Minimum',
                'Maximum'
            ]),
            defaultValue=0))

        self.addParameter(QgsProcessingParameterNumber(
            self.SIZE,
            self.tr('Window Size (Pixels)'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=3))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Filtered')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from scipy.ndimage import uniform_filter, median_filter, minimum_filter, maximum_filter
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.ndimage')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        bands = self.parameterAsInts(parameters, self.BANDS, context)
        filter_type = self.parameterAsInt(parameters, self.FILTER_TYPE, context)
        size = self.parameterAsInt(parameters, self.SIZE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if filter_type == SimpleRasterFilterType.MEAN_FILTER:

            from scipy.ndimage import uniform_filter as ndfilter

        elif filter_type == SimpleRasterFilterType.MEDIAN_FILTER:

            from scipy.ndimage import median_filter as ndfilter

        elif filter_type == SimpleRasterFilterType.MIN_FILTER:

            from scipy.ndimage import minimum_filter as ndfilter

        elif filter_type == SimpleRasterFilterType.MAX_FILTER:

            from scipy.ndimage import maximum_filter as ndfilter

        else:

            feedback.reportError(self.tr("Unknown filter type : %d") % filter_type, True)
            return {}

        ds = gdal.OpenEx(raster.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        transform = ds.GetGeoTransform()

        driver_name = GdalUtils.getFormatShortNameFromFilename(output)
        driver = gdal.GetDriverByName(driver_name or 'GTiff')

        dst = driver.Create(
            output,
            xsize=ds.RasterXSize,
            ysize=ds.RasterYSize,
            bands=len(bands),
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.SetProjection(ds.GetProjection())

        total = 100.0 / len(bands) if bands else 0.0

        for i, n in enumerate(bands):

            if feedback.isCanceled():
                break

            band = ds.GetRasterBand(n)
            data = band.ReadAsArray()
            nodata = band.GetNoDataValue()

            # data[data == nodata] = np.nan
            out = ndfilter(data, size)
            out[data == nodata] = nodata

            dst_band = dst.GetRasterBand(i+1)
            dst_band.WriteArray(out)
            dst_band.SetNoDataValue(nodata)
            del dst_band

            feedback.setProgress(int(i*total))

        ds = dst = None

        return {self.OUTPUT: output}
