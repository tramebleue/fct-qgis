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

import gdal

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ...lib.flow_accumulation import flow_accumulation
from ..metadata import AlgorithmMetadata

class FlowAccumulation(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Compute flow accumulation raster.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FlowAccumulation')

    FLOW = 'FLOW'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Accumulation Raster')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()
        # nodata = flow_ds.GetRasterBand(1).GetNoDataValue()

        out = flow_accumulation(
            flow,
            feedback=feedback)

        driver = gdal.GetDriverByName('GTiff')
        dst = driver.CreateCopy(output, flow_ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        # Properly close GDAL resources
        flow_ds = None
        dst = None

        return {self.OUTPUT: output}
