# -*- coding: utf-8 -*-

"""
Fill Depressions

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
    QgsProcessingParameterDistance,
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

class FillDepressions(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Fill depressions in input DEM.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FillDepressions')

    DEM = 'DEM'
    ZDELTA = 'ZDELTA'
    OUTPUT = 'OUTPUT'
    FLOW = 'FLOW'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.DEM,
            self.tr('Digital Elevation Model (DEM)')))

        self.addParameter(QgsProcessingParameterDistance(
            self.ZDELTA,
            self.tr('Minimun Z Delta'),
            parentParameterName=self.DEM,
            defaultValue=0.0))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Depression-Filled DEM')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.FLOW,
            self.tr('Flow Direction (D8)'),
            optional=True,
            createByDefault=False))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import fillsinks
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from ...lib.terrain_analysis import fillsinks

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.DEM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        flow_output = self.parameterAsOutputLayer(parameters, self.FLOW, context)
        zdelta = self.parameterAsDouble(parameters, self.ZDELTA, context)

        driver = gdal.GetDriverByName('GTiff')

        elevations_ds = gdal.OpenEx(elevations_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        elevations = np.float32(elevations_ds.GetRasterBand(1).ReadAsArray())

        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()
        transform = elevations_ds.GetGeoTransform()

        if flow_output:
            flow = np.zeros_like(elevations, dtype=np.int16)
        else:
            flow = None

        out = fillsinks(elevations, nodata, zdelta, flow=flow, feedback=feedback)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(0)
        feedback.pushInfo(self.tr('Write Filled DEM'))

        dst = driver.Create(
            output,
            xsize=elevations_ds.RasterXSize,
            ysize=elevations_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])

        dst.SetGeoTransform(transform)
        dst.SetProjection(elevations_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        dst = None

        feedback.setProgress(50)
        feedback.pushInfo(self.tr('Write Flow Direction'))

        if flow_output:

            dst = driver.Create(
                flow_output,
                xsize=elevations_ds.RasterXSize,
                ysize=elevations_ds.RasterYSize,
                bands=1,
                eType=gdal.GDT_Int16,
                options=['TILED=YES', 'COMPRESS=DEFLATE'])

            dst.SetGeoTransform(transform)
            dst.SetProjection(elevations_lyr.crs().toWkt())
            dst.GetRasterBand(1).WriteArray(flow)
            dst.GetRasterBand(1).SetNoDataValue(-1)

            # Properly close GDAL resources
            dst = None

        feedback.setProgress(100)

        # Properly close GDAL resources
        elevations_ds = None
        dst = None

        return {
            self.OUTPUT: output,
            self.FLOW: flow_output
        }
