# -*- coding: utf-8 -*-

"""
Burn Flow Direction

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

from qgis.core import ( # pylint:disable=no-name-in-module,import-error
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class BurnFlowDirection(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Burn linestring directions into an existing flow direction raster.

    This algorithm does not interpolate values between linestring vertices,
    ie. input vertices are expected to match raster cells,
    as produced by the `DrapeVectors` algorithm.

    Input raster will be converted to int16.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'BurnFlowDirection')

    INPUT = 'INPUT'
    BAND = 'BAND'
    LINESTRING = 'LINESTRING'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterBand(
            self.BAND,
            self.tr('Band'),
            parentLayerParameterName=self.INPUT,
            defaultValue=1))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LINESTRING,
            self.tr('LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Burned Flow Direction')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        layer = self.parameterAsSource(parameters, self.LINESTRING, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText(self.tr('Read input flow direction'))

        raster_path = str(raster.dataProvider().dataSourceUri())
        datasource = gdal.OpenEx(raster_path, gdal.GA_ReadOnly)
        data = np.int16(datasource.GetRasterBand(band).ReadAsArray())
        src_nodata = datasource.GetRasterBand(band).GetNoDataValue()
        transform = datasource.GetGeoTransform()

        def worldtopixel(x, y):
            """
            Transform real world coordinates (x, y)
            into raster pixel coordinates (row, col)
            """
            col = round((x - transform[0]) / transform[1] - 0.5)
            row = round((y - transform[3]) / transform[5] - 0.5)
            return row, col

        flow_directions = np.array([
            [128, 1, 2],
            [64, 0, 4],
            [32, 16, 8]], dtype=np.int16)

        feedback.setProgressText(self.tr('Burn flow direction'))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            linestring = feature.geometry()
            previous_row = previous_col = None

            for vertex in linestring.vertices():

                if previous_row is None:
                    previous_row, previous_col = worldtopixel(vertex.x(), vertex.y())
                    continue
                else:
                    row, col = worldtopixel(vertex.x(), vertex.y())

                if row == previous_row and col == previous_col:
                    continue

                delta_row = row - previous_row
                delta_col = col - previous_col

                if all([
                        delta_row >= -1, delta_row <= 1,
                        delta_col >= -1, delta_col <= 1,
                        previous_row >= 0, previous_row < datasource.RasterYSize,
                        previous_col >= 0, previous_col < datasource.RasterXSize
                    ]):

                    # pylint:disable=unsupported-assignment-operation
                    data[previous_row, previous_col] = flow_directions[delta_row+1, delta_col+1]

                previous_row, previous_col = row, col

        feedback.setProgressText(self.tr('Write output raster'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=datasource.RasterXSize,
            ysize=datasource.RasterYSize,
            bands=1,
            eType=gdal.GDT_Int16,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.GetRasterBand(1).WriteArray(data)
        dst.SetProjection(datasource.GetProjection())
        dst.GetRasterBand(1).SetNoDataValue(src_nodata)

        del datasource
        del dst

        return {self.OUTPUT: output}
