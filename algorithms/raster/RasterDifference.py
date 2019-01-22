# -*- coding: utf-8 -*-

"""
RasterDifference

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from qgis.analysis import ( # pylint:disable=no-name-in-module
    QgsRasterCalculator,
    QgsRasterCalculatorEntry
)

from processing.algs.gdal.GdalUtils import GdalUtils # pylint:disable=import-error
from ..metadata import AlgorithmMetadata

class RasterDifference(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Computes the difference between two rasters :
    Raster 1 - Raster 2
    """

    METADATA = AlgorithmMetadata.read(__file__, 'RasterDifference')

    RASTER1 = 'RASTER1'
    BAND1 = 'BAND1'
    RASTER2 = 'RASTER2'
    BAND2 = 'BAND2'
    OUTPUT = 'OUTPUT'
    USE_GDAL = 'USE_GDAL'

    def initAlgorithm(self, config=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER1,
            self.tr('Raster 1')))

        self.addParameter(QgsProcessingParameterBand(
            self.BAND1,
            self.tr('Raster 1 Band'),
            parentLayerParameterName=self.RASTER1,
            defaultValue=1))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER2,
            self.tr('Raster 2')))

        self.addParameter(QgsProcessingParameterBand(
            self.BAND2,
            self.tr('Raster 2 Band'),
            parentLayerParameterName=self.RASTER2,
            defaultValue=1))

        self.addParameter(QgsProcessingParameterBoolean(
            self.USE_GDAL,
            self.tr('Process With GDAL'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Difference')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        use_gdal = self.parameterAsBool(parameters, self.USE_GDAL, context)

        if use_gdal:
            return self.processWithGDAL(parameters, context, feedback)

        return self.processWithRasterCalculator(parameters, context, feedback)

    def processWithGDAL(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        import gdal
        import numpy as np

        raster1 = self.parameterAsRasterLayer(parameters, self.RASTER1, context)
        band1 = self.parameterAsInt(parameters, self.BAND1, context)
        raster2 = self.parameterAsRasterLayer(parameters, self.RASTER2, context)
        band2 = self.parameterAsInt(parameters, self.BAND2, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        raster1_path = str(raster1.dataProvider().dataSourceUri())
        raster2_path = str(raster2.dataProvider().dataSourceUri())

        ds1 = gdal.OpenEx(raster1_path)

        data1 = ds1.GetRasterBand(band1).ReadAsArray()
        nodata1 = ds1.GetRasterBand(band1).GetNoDataValue()

        # reference = gn.LoadFile(reference_dem_path)
        ds2 = gdal.OpenEx(raster2_path)

        data2 = ds2.GetRasterBand(band2).ReadAsArray()
        nodata2 = ds2.GetRasterBand(band2).GetNoDataValue()
        if nodata2 is None:
            nodata2 = nodata1

        difference = data1 - data2
        difference[(data1 == nodata1)|(data2 == nodata2)] = nodata1
        # difference[data2 == nodata2] = nodata1

        driver = gdal.GetDriverByName('GTiff')
        # dst = driver.CreateCopy(
        #     str(output),
        #     ds1,
        #     strict=0,
        #     options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst = driver.Create(
            output,
            xsize=ds1.RasterXSize,
            ysize=ds1.RasterYSize,
            bands=1,
            eType=ds1.GetRasterBand(band1).DataType,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(ds1.GetGeoTransform())
        dst.SetProjection(raster1.crs().toWkt())

        # Write data
        dst.GetRasterBand(1).WriteArray(difference)
        dst.GetRasterBand(1).SetNoDataValue(nodata1)

        # Properly close GDAL resources
        ds1 = None
        ds2 = None
        dst = None

        return {self.OUTPUT: output}

    def processWithRasterCalculator(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster1 = self.parameterAsRasterLayer(parameters, self.RASTER1, context)
        band1 = self.parameterAsInt(parameters, self.BAND1, context)
        raster2 = self.parameterAsRasterLayer(parameters, self.RASTER2, context)
        band2 = self.parameterAsInt(parameters, self.BAND2, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        bbox = raster1.extent()
        # cellsize = (bbox.xMaximum() - bbox.xMinimum()) / raster1.width()
        # width = round((bbox.xMaximum() - bbox.xMinimum()) / cellsize)
        # height = round((bbox.yMaximum() - bbox.yMinimum()) / cellsize)
        width = raster1.width()
        height = raster1.height()
        driver = GdalUtils.getFormatShortNameFromFilename(output)
        crs = raster1.crs()

        entry1 = QgsRasterCalculatorEntry()
        entry1.ref = 'A@%d' % band1
        entry1.raster = raster1
        entry1.bandNumber = 1

        entry2 = QgsRasterCalculatorEntry()
        entry2.ref = 'B@%d' % band2
        entry2.raster = raster2
        entry2.bandNumber = 1

        entries = [entry1, entry2]
        expression = "A@%d - B@%d" % (band1, band2)

        calc = QgsRasterCalculator(expression,
                                   output,
                                   driver,
                                   bbox,
                                   crs,
                                   width,
                                   height,
                                   entries)

        res = calc.processCalculation(feedback)
        if res == QgsRasterCalculator.ParserError:
            raise QgsProcessingException(self.tr("Error parsing formula"))

        return {self.OUTPUT: output}
