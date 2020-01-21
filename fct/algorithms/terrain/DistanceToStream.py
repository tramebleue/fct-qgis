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
    QgsProcessingParameterFeatureSource,
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

class DistanceToStream(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Calculate distance to the nearest stream cell (Raster).
    """

    METADATA = AlgorithmMetadata.read(__file__, 'DistanceToStream')

    INPUT = 'INPUT'
    STREAM = 'STREAM'
    SIGNED_DISTANCE = 'SIGNED_DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Template Raster')))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.STREAM,
            self.tr('Stream LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterBoolean(
            self.SIGNED_DISTANCE,
            self.tr('Calculate Signed Distance ?'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Distance To Stream')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint:disable=import-error,no-name-in-module,unused-variable
            import scipy.spatial
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.spatial')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from scipy.spatial import cKDTree

        # if CYTHON:
        #     feedback.pushInfo("Using Cython flow_accumulation() ...")
        # else:
        #     feedback.pushInfo("Pure python flow_accumulation() - this may take a while ...")

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        stream_layer = self.parameterAsSource(parameters, self.STREAM, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        signed = self.parameterAsBool(parameters, self.SIGNED_DISTANCE, context)

        feedback.setProgressText('Read elevations')

        elevations_ds = gdal.OpenEx(elevations_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()
        transform = elevations_ds.GetGeoTransform()
        height, width = elevations.shape

        feedback.setProgressText('Build stream point index')
        stream_points = list()
        directions = list()
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
                
                stream_points.extend([
                    (py, px, len(directions)) for px, py
                    in rasterize_linestring(a, b)
                    if isdata(int(round(px)), int(round(py)))
                ][:-1])

                # Axis are reversed in pixel coord !
                direction = (b - a)
                directions.append((direction[1], direction[0]))

            # Add a separator point at Infinity between linestrings
            # stream_points.append((np.infty, np.infty, 0))

        stream_points = np.array(stream_points)
        directions = np.array(directions)
        point_index = cKDTree(stream_points[:, 0:2], balanced_tree=True)

        feedback.setProgressText('Calculate distance to nearest stream cell')
        out = np.zeros_like(elevations)
        height, width = elevations.shape
        total = 100.0 / height if height else 0.0

        for row in range(height):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(row*total))

            coords = np.int32([row*np.ones(width, dtype=np.int32), np.arange(width)]).T
            distance, nearest = point_index.query(coords)
            nearest_points = np.take(stream_points[:, :2], nearest, axis=0, mode='wrap')
            diff = coords - nearest_points
            map_distance = np.linalg.norm(diff * [transform[5], transform[1]], axis=1)

            if signed:

                nearest_dir_idx = np.uint32(np.take(stream_points[:, 2], nearest, axis=0, mode='wrap'))
                nearest_dir = np.take(directions, nearest_dir_idx, axis=0, mode='wrap')
                out[row, :] = np.sign(np.cross(nearest_dir, diff)) * map_distance

            else:

                out[row, :] = map_distance

        out[elevations == nodata] = nodata

        feedback.setProgress(100)
        feedback.setProgressText(self.tr('Write output ...'))

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

        dst.GetRasterBand(1).WriteArray(np.asarray(out))
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        elevations_ds = None
        dst = None

        return {self.OUTPUT: output}
