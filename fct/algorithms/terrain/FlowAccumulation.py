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

import numpy as np
from osgeo import gdal
# import osr

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

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

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import flow_accumulation
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from ...lib.terrain_analysis import flow_accumulation

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()
        nodata = flow_ds.GetRasterBand(1).GetNoDataValue()

        # epsg = flow_ds.crs().authid().split(':')[1]
        # srs = osr.SpatialReference()
        # srs.ImportFromEPSG(epsg)

        out = flow_accumulation(flow, feedback=feedback)
        out[flow == nodata] = 0

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')
        # dst = driver.CreateCopy(output, flow_ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst = driver.Create(
            output,
            xsize=flow_ds.RasterXSize,
            ysize=flow_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_UInt32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(flow_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(flow_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(np.asarray(out))
        dst.GetRasterBand(1).SetNoDataValue(0)

        # Properly close GDAL resources
        flow_ds = None
        dst = None

        return {self.OUTPUT: output}
