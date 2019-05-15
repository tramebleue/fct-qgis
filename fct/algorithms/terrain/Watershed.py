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
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from processing.core.ProcessingConfig import ProcessingConfig
from ..metadata import AlgorithmMetadata

class Watershed(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Fills no-data cells in Target Raster
    by propagating data values in the inverse (ie. upward) flow direction
    given by D8-encoded Flow Direction.

    In typical usage,
    the `Target Raster` is the Strahler order for stream cells and no data elsewhere,
    and the result is a raster map of watersheds, identified by their Strahler order.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'Watershed')

    FLOW = 'FLOW'
    TARGET = 'TARGET'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.TARGET,
            self.tr('Target Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Watersheds')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        if ProcessingConfig.getSetting('FCT_ACTIVATE_CYTHON'):
            try:
                from ...lib.terrain_analysis import watershed
                with_cython = True
            except ImportError:
                from ...lib.watershed import watershed
                with_cython = False
        else:
            from ...lib.watershed import watershed
            with_cython = False

        if with_cython:
            feedback.pushInfo("Using Cython watershed() ...")
        else:
            feedback.pushInfo("Using pure python watershed() - this may take a while ...")

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        target_lyr = self.parameterAsRasterLayer(parameters, self.TARGET, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        target_ds = gdal.Open(target_lyr.dataProvider().dataSourceUri())
        nodata = target_ds.GetRasterBand(1).GetNoDataValue()
        # TODO check target dtype
        target = np.float32(target_ds.GetRasterBand(1).ReadAsArray())

        watershed(flow, target, feedback=feedback)
        
        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')
        dst = driver.CreateCopy(output, target_ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])

        dst.GetRasterBand(1).WriteArray(target)

        # Properly close GDAL resources
        flow_ds = None
        target_ds = None
        dst = None

        return {self.OUTPUT: output}
