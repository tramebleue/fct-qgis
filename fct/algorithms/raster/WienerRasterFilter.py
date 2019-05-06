# -*- coding: utf-8 -*-

"""
Wiener Filter (Smoothing)

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

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from processing.algs.gdal.GdalUtils import GdalUtils # pylint:disable=import-error
from ..metadata import AlgorithmMetadata

class WienerRasterFilter(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Apply a Wiener filter to raster.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'WienerRasterFilter')

    INPUT = 'INPUT'
    BANDS = 'BANDS'
    SIZE = 'SIZE'
    NOISE = 'NOISE'
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

        self.addParameter(QgsProcessingParameterNumber(
            self.SIZE,
            self.tr('Window Size (Pixels)'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=3))

        self.addParameter(QgsProcessingParameterNumber(
            self.NOISE,
            self.tr('Noise Power'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0,
            optional=True))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Filtered (Wiener)')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from scipy.signal import wiener
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.signal')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        bands = self.parameterAsInts(parameters, self.BANDS, context)
        size = self.parameterAsInt(parameters, self.SIZE, context)
        noise = self.parameterAsDouble(parameters, self.NOISE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if noise is not None and noise <= 0:
            feedback.reportError(self.tr('Noise power shoud be a positive double value or None'), False)
            noise = None

        from scipy.signal import wiener

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

            out = wiener(data, size, noise)
            out[data == nodata] = nodata

            dst_band = dst.GetRasterBand(i+1)
            dst_band.WriteArray(out)
            dst_band.SetNoDataValue(nodata)
            del dst_band

            feedback.setProgress(int(i*total))

        ds = dst = None

        return {self.OUTPUT: output}
