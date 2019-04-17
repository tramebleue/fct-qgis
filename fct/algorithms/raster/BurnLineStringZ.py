# -*- coding: utf-8 -*-

"""
BurnLineStringZ

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

class BurnLineStringZ(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Burn raster with linestring Z values.

    This algorithm does not interpolate values between linestring vertices,
    input vertices are expected to match raster cells,
    as produced by the `DrapeVectors` algorithm.

    Input raster will be converted to float32.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'BurnLineStringZ')

    INPUT = 'INPUT'
    BAND = 'BAND'
    LINESTRINGZ = 'LINESTRINGZ'
    NODATA = 'NODATA'
    OFFSET = 'OFFSET'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Input Raster')))

        self.addParameter(QgsProcessingParameterBand(
            self.BAND,
            self.tr('Band'),
            parentLayerParameterName=self.INPUT,
            defaultValue=1))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LINESTRINGZ,
            self.tr('LineString With Z'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterNumber(
            self.NODATA,
            self.tr('LineString Z No-Data Value'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=-99999.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.OFFSET,
            self.tr('Offset to add to Z values'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.0))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Burned Raster')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        layer = self.parameterAsSource(parameters, self.LINESTRINGZ, context)
        nodata = self.parameterAsDouble(parameters, self.NODATA, context)
        offset = self.parameterAsDouble(parameters, self.OFFSET, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        if not QgsWkbTypes.hasZ(layer.wkbType()):
            feedback.reportError(self.tr('Linestrings must have Z coordinate.'), True)
            return {}

        feedback.setProgressText(self.tr('Read input raster'))

        raster_path = str(raster.dataProvider().dataSourceUri())
        datasource = gdal.OpenEx(raster_path, gdal.GA_ReadOnly)
        data = np.float32(datasource.GetRasterBand(band).ReadAsArray())
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

        feedback.setProgressText(self.tr('Burn linestrings'))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            linestring = feature.geometry()

            for vertex in linestring.vertices():

                z = vertex.z()
                if z == nodata:
                    continue

                row, col = worldtopixel(vertex.x(), vertex.y())
                data[row, col] = z + offset

        feedback.setProgressText(self.tr('Write output raster'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=datasource.RasterXSize,
            ysize=datasource.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.GetRasterBand(1).WriteArray(data)
        dst.SetProjection(datasource.GetProjection())
        dst.GetRasterBand(1).SetNoDataValue(src_nodata)

        del datasource
        del dst

        return {self.OUTPUT: output}
