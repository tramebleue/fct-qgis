# -*- coding: utf-8 -*-

"""
Relative Digital Elevation Model (DEM)

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
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
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

            yield int(round(x)), int(round(y))

            x = x + dx
            y = y + dy
            i += 1

    else:

        yield a[0], a[1]

def pixeltoworld(sequence, transform):
    """
    Transform raster pixel coordinates (px, py)
    into real world coordinates (x, y)
    """
    return (sequence + 0.5)*[transform[1], transform[5]] + [transform[0], transform[3]]

def worldtopixel(sequence, transform):
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (px, py)
    """
    return np.int32(np.round((sequence - [transform[0], transform[3]]) / [transform[1], transform[5]] - 0.5))

class StreamToRaster(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Rasterize stream vectors,
    on a new Float32 raster with same dimensions and georeferencing
    as the provided raster template.
    
    When there is a collision between two streams on the same cell,
    priority is given to the stream with the smallest ID.

    Non-stream cells are filled with zeros.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StreamToRaster')

    INPUT = 'INPUT'
    PK_FIELD = 'PK_FIELD'
    RASTER_TEMPLATE = 'RASTER_TEMPLATE'
    METHOD = 'METHOD'
    FILL_VALUE = 'FILL_VALUE'
    BURN_VALUE = 'BURN_VALUE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Stream Primary Key'),
            parentLayerParameterName=self.INPUT,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER_TEMPLATE,
            self.tr('Raster Template/Data')))

        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD,
            self.tr('Get Values From'),
            options=[self.tr(option) for option in ['Vector Id Field', 'Source Raster', 'Burn fixed value']],
            defaultValue=0))

        self.addParameter(QgsProcessingParameterNumber(
            self.FILL_VALUE,
            self.tr('Fill Value'),
            defaultValue=0
        ))

        self.addParameter(QgsProcessingParameterNumber(
            self.BURN_VALUE,
            self.tr('Optional Burn Value'),
            defaultValue=1.0
        ))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Rasterized Streams')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        template_lyr = self.parameterAsRasterLayer(parameters, self.RASTER_TEMPLATE, context)
        layer = self.parameterAsSource(parameters, self.INPUT, context)
        pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        method = self.parameterAsInt(parameters, self.METHOD, context)
        fill_value = self.parameterAsDouble(parameters, self.FILL_VALUE, context)
        burn_value = self.parameterAsDouble(parameters, self.BURN_VALUE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        template_ds = gdal.OpenEx(template_lyr.dataProvider().dataSourceUri())
        nodata = template_ds.GetRasterBand(1).GetNoDataValue()
        transform = template_ds.GetGeoTransform()
        width = template_ds.RasterXSize
        height = template_ds.RasterYSize

        feedback.setProgressText('Rasterize stream vectors')
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        data = template_ds.GetRasterBand(1).ReadAsArray()
        streams = np.zeros((height, width), dtype=np.float32)
        out = np.full((height, width), fill_value, dtype=np.float32)

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate
            """

            return px >= 0 and py >= 0 and px < width and py < height

        if method == 0:

            def set_data(row, col):
                """
                Set Pixel Value to Line Primary Field
                """

                current_value = streams[row, col]

                if current_value == 0 or link_id < current_value:
                    # Override with the smallest ID
                    streams[row, col] = link_id
                    out[row, col] = link_id

        elif method == 1:

            def set_data(row, col):
                """
                Set Pixel Value to Template Raster Value
                """

                out[row, col] = data[row, col]

        elif method == 2:

            def set_data(row, col):
                """
                Set Pixel Value to Fixed Value
                """

                out[row, col] = burn_value


        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            link_id = feature.attribute(pk_field)

            linestring = worldtopixel(np.array([
                (point.x(), point.y())
                for point in feature.geometry().asPolyline()
            ]), transform)

            for a, b in zip(linestring[:-1], linestring[1:]):
                for col, row in rasterize_linestring(a, b):
                    if isdata(col, row):
                        set_data(row, col)

        feedback.setProgress(100)
        feedback.setProgressText(self.tr('Write output ...'))

        if nodata is None:
            nodata = -99999
        else:
            out[data == nodata] = nodata

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=template_ds.RasterXSize,
            ysize=template_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.SetProjection(template_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        template_ds = None
        dst = None

        return {self.OUTPUT: output}
