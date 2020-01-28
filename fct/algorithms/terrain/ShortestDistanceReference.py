# -*- coding: utf-8 -*-

"""
Distance To Nearest Stream Cell (Raster)

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
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

def rasterize_linestring(a, b):
    """
    Returns projected segment
    as a sequence of (px, py) coordinates.

    See https://en.wikipedia.org/wiki/Bresenham%27s_line_algorithm

    Parameters
    ----------

    a, b: vector of coordinate pair
        end points of segment [AB]

    Returns
    -------

    Generator of (x, y) coordinates
    corresponding to the intersection of raster cells with segment [AB],
    yielding one data point per intersected cell.
    """

    dx = abs(b[0] - a[0])
    dy = abs(b[1] - a[1])

    if dx > 0 or dy > 0:

        if dx > dy:
            count = dx
            dx = 1.0
            dy = dy / count
        else:
            count = dy
            dy = 1.0
            dx = dx / count

        if a[0] > b[0]:
            dx = -dx
        if a[1] > b[1]:
            dy = -dy

        x = float(a[0])
        y = float(a[1])
        i = 0

        while i < count+1:

            # yield int(round(x)), int(round(y))
            yield x, y

            x = x + dx
            y = y + dy
            i += 1

    else:

        yield a[0], a[1]

def pixeltoworld(sequence, transform):
    """
    Transform raster pixel coordinates (py, px)
    into real world coordinates (x, y)
    """
    return (np.fliplr(sequence) + 0.5)*[transform[1], transform[5]] + [transform[0], transform[3]]

def worldtopixel(sequence, transform):
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (px, py)
    """
    # return np.int32(np.round((sequence - [transform[0], transform[3]]) / [transform[1], transform[5]] - 0.5))
    return (sequence - [transform[0], transform[3]]) / [transform[1], transform[5]] - 0.5

class ShortestDistanceReference(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Calculate distance to the nearest stream cell (Raster).
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ShortestDistanceReference')

    INPUT = 'INPUT'
    FILL_VALUE = 'FILL_VALUE'
    # SIGNED_DISTANCE = 'SIGNED_DISTANCE'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Target Raster')))

        self.addParameter(QgsProcessingParameterNumber(
            self.FILL_VALUE,
            self.tr('Fill Value'),
            defaultValue=-99999))

        # self.addParameter(QgsProcessingParameterBoolean(
        #     self.SIGNED_DISTANCE,
        #     self.tr('Calculate Signed Distance ?'),
        #     defaultValue=False))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Shortest Distance Reference')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.DISTANCE,
            self.tr('Shortest Distance'),
            optional=True))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib import terrain_analysis as ta
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from ...lib import terrain_analysis as ta

        input_lyr = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        fill_value = self.parameterAsDouble(parameters, self.FILL_VALUE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        dist_output = self.parameterAsOutputLayer(parameters, self.DISTANCE, context)
        # signed = self.parameterAsBool(parameters, self.SIGNED_DISTANCE, context)

        feedback.setProgressText('Read input raster')

        input_ds = gdal.OpenEx(input_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        data = input_ds.GetRasterBand(1).ReadAsArray()
        nodata = input_ds.GetRasterBand(1).GetNoDataValue()
        transform = input_ds.GetGeoTransform()
        resolution_x = transform[1]
        resolution_y = -transform[5]
        height, width = data.shape

        feedback.setProgressText('Calculate shortest distance')

        origins = np.float32(data != fill_value)
        origins[data == nodata] = nodata
        distance = np.zeros_like(data)
        
        ta.shortest_ref(origins, nodata, startval=1, fillval=fill_value, out=data, distance=distance, feedback=feedback)
        distance = np.asarray(distance) * (0.5 * (resolution_x + resolution_y))
        distance[data == nodata] = nodata

        feedback.setProgress(100)
        feedback.setProgressText(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=input_ds.RasterXSize,
            ysize=input_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(input_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(input_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(data)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        dst = None

        if dist_output is not None:

            dst = driver.Create(
                dist_output,
                xsize=input_ds.RasterXSize,
                ysize=input_ds.RasterYSize,
                bands=1,
                eType=gdal.GDT_Float32,
                options=['TILED=YES', 'COMPRESS=DEFLATE'])
            dst.SetGeoTransform(input_ds.GetGeoTransform())
            # dst.SetProjection(srs.exportToWkt())
            dst.SetProjection(input_lyr.crs().toWkt())

            dst.GetRasterBand(1).WriteArray(distance)
            dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        input_ds = None
        dst = None

        return {self.OUTPUT: output}
