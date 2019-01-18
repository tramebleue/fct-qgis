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

    METADATA = AlgorithmMetadata.read(__file__, 'RasterDifference')

    RASTER1 = 'RASTER1'
    RASTER2 = 'RASTER2'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER1,
            self.tr('Raster 1')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER2,
            self.tr('Raster 2')))
        
        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Difference')))

    def processAlgorithm(self, parameters, context, feedback):

        return self.processWithRasterCalculator(parameters, context, feedback)
        # return self.processWithGDAL(parameters, context, feedback)

    def processWithGDAL(self, parameters, context, feedback):

        import gdal
        import numpy as np

        raster1 = self.parameterAsRasterLayer(parameters, self.RASTER1, context)
        raster2 = self.parameterAsRasterLayer(parameters, self.RASTER2, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        raster1_path = str(raster1.dataProvider().dataSourceUri())
        raster2_path = str(raster2.dataProvider().dataSourceUri())

        ds1 = gdal.Open(raster1_path)
        if ds1.RasterCount != 1:
            feedback.pushInfo('Raster 1 has more than 1 band.')

        data1 = ds1.GetRasterBand(1).ReadAsArray()
        nodata1 = ds1.GetRasterBand(1).GetNoDataValue()

        # reference = gn.LoadFile(reference_dem_path)
        ds2 = gdal.Open(raster2_path)
        if ds2.RasterCount != 1:
            feedback.pushInfo('Raster 2 has more than 1 band.')

        data2 = ds2.GetRasterBand(1).ReadAsArray()
        nodata2 = ds2.GetRasterBand(1).GetNoDataValue()
        if nodata2 is None:
            nodata2 = nodata1

        difference = data1 - data2
        difference[(data1 == nodata1)|(data2 == nodata2)] = nodata1
        # difference[data2 == nodata2] = nodata1

        driver = gdal.GetDriverByName('GTiff')
        dst = driver.CreateCopy(str(output), ds1, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.GetRasterBand(1).WriteArray(difference)

        # Properly close GDAL resources
        ds1 = None
        ds2 = None
        dst = None

        return {self.OUTPUT: output}

    def processWithRasterCalculator(self, parameters, context, feedback):

        raster1 = self.parameterAsRasterLayer(parameters, self.RASTER1, context)
        raster2 = self.parameterAsRasterLayer(parameters, self.RASTER2, context)
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
        entry1.ref = 'A@1'
        entry1.raster = raster1
        entry1.bandNumber = 1

        entry2 = QgsRasterCalculatorEntry()
        entry2.ref = 'B@1'
        entry2.raster = raster2
        entry2.bandNumber = 1

        entries = [entry1, entry2]
        expression = "A@1 - B@1"

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
