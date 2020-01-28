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
    QgsProcessingParameterFeatureSource,
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

def remove_duplicates(points):
    """
    Remove duplicate vertices in sequence.
    """

    if points:

        new_points = list()
        x, y, z = points[0]
        new_points.append((x, y, z))

        for nx, ny, nz in points[1:]:
            if nx != x or ny != y:
                new_points.append((nx, ny, nz))
                x, y = nx, ny

        return new_points

    return []

class HeightAboveNearestDrainageCombined(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Calculate elevations relative to stream cells
    (aka. detrended DEM)
    """

    METADATA = AlgorithmMetadata.read(__file__, 'HeightAboveNearestDrainageCombined')

    INPUT = 'INPUT'
    STREAM = 'STREAM'
    WATERSHEDS = 'WATERSHEDS'
    FLOW = 'FLOW'
    SLOPE = 'SLOPE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Digital Elevation Model (DEM)')))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.STREAM,
            self.tr('Stream LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.WATERSHEDS,
            self.tr('Watersheds')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction (D8)')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.SLOPE,
            self.tr('Slope Class')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Relative Elevation')))


    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from ...lib import terrain_analysis as ta

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        watersheds_lyr = self.parameterAsRasterLayer(parameters, self.WATERSHEDS, context)
        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        slope_lyr = self.parameterAsRasterLayer(parameters, self.SLOPE, context)
        stream_layer = self.parameterAsSource(parameters, self.STREAM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText('Read elevations')

        elevations_ds = gdal.Open(elevations_lyr.dataProvider().dataSourceUri())
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()
        transform = elevations_ds.GetGeoTransform()
        height, width = elevations.shape

        feedback.setProgressText('Read watersheds')

        watersheds_ds = gdal.Open(watersheds_lyr.dataProvider().dataSourceUri())
        watersheds = watersheds_ds.GetRasterBand(1).ReadAsArray()

        feedback.setProgressText('Build stream point index')

        refz = np.zeros_like(elevations)
        total = 100.0 / stream_layer.featureCount() if stream_layer.featureCount() else 0.0

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate,
            and is not a no-data value.
            """

            if px < 0 or py < 0 or px >= width or py >= height:
                return False

            return elevations[py, px] != nodata

        for current, feature in enumerate(stream_layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            linestring = worldtopixel(np.array([
                (point.x(), point.y())
                for point in feature.geometry().asPolyline()
            ]), transform)

            for a, b in zip(linestring[:-1], linestring[1:]):
                for px, py in rasterize_linestring(a, b):
                    if isdata(px, py):
                        refz[py, px] = elevations[py, px]

        feedback.setProgressText('Calculate relative elevations')

        data = np.float32(refz != 0)
        data[elevations == nodata] = nodata
        ta.shortest_ref_ws(data, watersheds, nodata, 1, out=refz, feedback=feedback)

        feedback.setProgressText('Calculate relative elevations (Step 2)')

        slope_ds = gdal.Open(slope_lyr.dataProvider().dataSourceUri())
        slope = slope_ds.GetRasterBand(1).ReadAsArray()

        refz[(slope > 2) & (data == 0)] = -99999

        del data
        del slope

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        ta.watershed(flow, refz, fill_value=-99999, feedback=feedback)

        feedback.setProgress(100)
        feedback.setProgressText(self.tr('Write output ...'))

        refz[refz == -99999] = 0
        refz = elevations - refz
        refz[elevations == nodata] = nodata

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=elevations_ds.RasterXSize,
            ysize=elevations_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(elevations_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(elevations_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(np.asarray(refz))
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        elevations_ds = None
        watersheds_ds = None
        flow_ds = None
        slope_ds = None
        dst = None

        return {self.OUTPUT: output}
