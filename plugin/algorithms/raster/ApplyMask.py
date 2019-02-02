# -*- coding: utf-8 -*-

"""
ApplyMask

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
    QgsProcessingException,
    # QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterString
)

from qgis.analysis import ( # pylint:disable=no-name-in-module
    QgsRasterCalculator,
    QgsRasterCalculatorEntry
)

from processing.algs.gdal.GdalUtils import GdalUtils # pylint:disable=import-error
from ..metadata import AlgorithmMetadata

class ApplyMask(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Set pixels outside mask to no-data.
    Mask condition can be expressed using the VALUE variable,
    for example `VALUE > 50.0`
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ApplyMask')

    INPUT = 'INPUT'
    NODATA = 'NODATA'
    MASK = 'MASK'
    MASK_EXPRESSION = 'MASK_EXPRESSION'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.MASK,
            self.tr('Mask')))

        self.addParameter(QgsProcessingParameterString(
            self.MASK_EXPRESSION,
            self.tr('Mask Condition')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Masked')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = 1
        mask = self.parameterAsRasterLayer(parameters, self.MASK, context)
        # nodata = self.parameterAsDouble(parameters, self.NODATA, context)
        mask_expression = self.parameterAsString(parameters, self.MASK_EXPRESSION, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        ds = gdal.Open(raster.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        nodata = ds.GetRasterBand(band).GetNoDataValue()

        bbox = raster.extent()
        # cellsize = (bbox.xMaximum() - bbox.xMinimum()) / raster1.width()
        # width = round((bbox.xMaximum() - bbox.xMinimum()) / cellsize)
        # height = round((bbox.yMaximum() - bbox.yMinimum()) / cellsize)
        width = raster.width()
        height = raster.height()
        driver = GdalUtils.getFormatShortNameFromFilename(output)
        crs = raster.crs()

        entry1 = QgsRasterCalculatorEntry()
        entry1.ref = 'A@1'
        entry1.raster = raster
        entry1.bandNumber = 1

        entry2 = QgsRasterCalculatorEntry()
        entry2.ref = 'B@1'
        entry2.raster = mask
        entry2.bandNumber = 1

        entries = [entry1, entry2]
        # print(nodata)

        expression = """
            (%(mask_expression)s)*A@1 + (1-(%(mask_expression)s))*%(nodata)f
        """ % {
            'mask_expression': mask_expression.replace('VALUE', 'B@1'),
            'nodata': nodata
        }

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

        # Ugly inefficient patch to handle that
        # QgsRasterCalculator does not set no-data properly

        in_data = ds.GetRasterBand(band).ReadAsArray()

        out_ds = gdal.OpenEx(output, gdal.OF_RASTER | gdal.OF_UPDATE)
        data = out_ds.GetRasterBand(1).ReadAsArray()
        data[in_data == nodata] = nodata

        out_ds.GetRasterBand(1).SetNoDataValue(nodata)
        out_ds.GetRasterBand(1).WriteArray(data)

        ds = out_ds = None

        return {self.OUTPUT: output}

