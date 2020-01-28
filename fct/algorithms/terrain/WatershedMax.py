# -*- coding: utf-8 -*-

"""
Watershed Analysis

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
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

class WatershedMax(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Fills no-data cells in Target Raster
    by propagating data values in the inverse (ie. upward) flow direction
    given by D8-encoded Flow Direction.

    In typical usage,
    the `Target Raster` is the Strahler order for stream cells and no data elsewhere,
    and the result is a raster map of watersheds, identified by their Strahler order.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'WatershedMax')

    FLOW = 'FLOW'
    TARGET = 'TARGET'
    REFERENCE = 'REFERENCE'
    FILL_VALUE = 'FILL_VALUE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.TARGET,
            self.tr('Target Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.REFERENCE,
            self.tr('Reference Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterNumber(
            self.FILL_VALUE,
            self.tr('Fill Value'),
            defaultValue=-99999))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Watersheds')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib import terrain_analysis as ta
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from ...lib import terrain_analysis as ta

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        target_lyr = self.parameterAsRasterLayer(parameters, self.TARGET, context)
        ref_lyr = self.parameterAsRasterLayer(parameters, self.REFERENCE, context)
        fill_value = self.parameterAsDouble(parameters, self.FILL_VALUE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        target_ds = gdal.Open(target_lyr.dataProvider().dataSourceUri())
        nodata = target_ds.GetRasterBand(1).GetNoDataValue()
        target = target_ds.GetRasterBand(1).ReadAsArray()
        transform = target_ds.GetGeoTransform()
        # width = target_ds.RasterXSize
        # height = target_ds.RasterYSize

        ref_ds = gdal.OpenEx(ref_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        reference = ref_ds.GetRasterBand(1).ReadAsArray()

        ta.watershed_max(flow, target, reference, fill_value=fill_value, feedback=feedback)

        # target[target == fill_value] = reference[target == fill_value]
        target[target == fill_value] = nodata

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=target_ds.RasterXSize,
            ysize=target_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Byte,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.SetProjection(target_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(target)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        flow_ds = None
        target_ds = None
        ref_ds = None
        dst = None

        return {self.OUTPUT: output}
