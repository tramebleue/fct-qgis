# -*- coding: utf-8 -*-

"""
Resolve Flat's Flow Direction

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

# try:
#     from ...lib.terrain_analysis import flow_accumulation
#     CYTHON = True
# except ImportError:
#     from ...lib.flow_accumulation import flow_accumulation
#     CYTHON = False

class ResolveFlats(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Resolve Flow Direction in flat areas,
    such as they are produced by filling depressions.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ResolveFlats')

    FILLED = 'FILLED'
    FLOW = 'FLOW'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FILLED,
            self.tr('Depression-Filled DEM')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Resolved Flow Direction')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import resolve_flat, flat_mask_flowdir
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # if CYTHON:
        #     feedback.pushInfo("Using Cython flow_accumulation() ...")
        # else:
        #     feedback.pushInfo("Pure python flow_accumulation() - this may take a while ...")

        from ...lib.terrain_analysis import resolve_flat, flat_mask_flowdir

        filled_lyr = self.parameterAsRasterLayer(parameters, self.FILLED, context)
        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        driver = gdal.GetDriverByName('GTiff')

        filled_ds = gdal.OpenEx(filled_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        filled = np.float32(filled_ds.GetRasterBand(1).ReadAsArray())
        transform = filled_ds.GetGeoTransform()

        flow_ds = gdal.OpenEx(flow_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        flow = np.int16(flow_ds.GetRasterBand(1).ReadAsArray())

        mask, flat_labels = resolve_flat(filled, flow, feedback)
        flat_mask_flowdir(mask, flow, flat_labels)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(50)
        feedback.pushInfo(self.tr('Write Flow Direction'))

        dst = driver.Create(
            output,
            xsize=filled_ds.RasterXSize,
            ysize=filled_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Int16,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])

        dst.SetGeoTransform(transform)
        dst.SetProjection(filled_lyr.crs().toWkt())
        dst.GetRasterBand(1).WriteArray(flow)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        feedback.setProgress(100)

        # Properly close GDAL resources
        filled_ds = None
        flow_ds = None
        dst = None

        return {
            self.OUTPUT: output
        }
