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
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata
from ...lib.terrain_analysis import watershed
from .SubGridTopography import worldtopixel

class SubGridMap(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Subgrid Feature Map
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SubGridMap')

    FLOW = 'FLOW'
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Subgrid Outlets'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Subgrid Map')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()
        transform = flow_ds.GetGeoTransform()
        height, width = flow.shape

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate
            """

            return px >= 0 and py >= 0 and px < width and py < height

        target = np.zeros_like(flow, dtype=np.float32)
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            outlet = feature.geometry().asPoint()
            px, py = worldtopixel(np.array([outlet.x(), outlet.y()]), transform)
            if isdata(px, py):
                target[py, px] = feature.id()

        watershed(flow, target, feedback=feedback)
        
        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')
        
        dst = driver.Create(
            output,
            xsize=flow_ds.RasterXSize,
            ysize=flow_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(flow_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(np.asarray(target))
        dst.GetRasterBand(1).SetNoDataValue(0)

        # Properly close GDAL resources
        flow_ds = None
        dst = None

        return {self.OUTPUT: output}
