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
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

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

class SignedShortestDistance(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Calculate distance to the nearest stream cell (Raster).
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SignedShortestDistance')

    INPUT = 'INPUT'
    DISTANCE = 'DISTANCE'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.DISTANCE,
            self.tr('Distance Raster')))

        self.addParameter(QgsProcessingParameterDistance(
            self.SEARCH_DISTANCE,
            self.tr('Maximum Search Distance'),
            parentParameterName=self.INPUT,
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Signed Distance')))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from scipy.spatial import cKDTree
            from ...lib import terrain_analysis as ta
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: SciPy or FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # pylint:disable=import-error,no-name-in-module
        from scipy.spatial import cKDTree
        from ...lib import terrain_analysis as ta

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        distance_lyr = self.parameterAsRasterLayer(parameters, self.DISTANCE, context)
        max_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText('Read distance raster')

        distance_ds = gdal.OpenEx(distance_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        distance = distance_ds.GetRasterBand(1).ReadAsArray()
        nodata = distance_ds.GetRasterBand(1).GetNoDataValue()
        transform = distance_ds.GetGeoTransform()
        height, width = distance.shape

        feedback.setProgressText('Build point/segment index')

        segments = list()
        midpoints = list()
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate,
            and is not a no-data value.
            """

            if px < 0 or py < 0 or px >= width or py >= height:
                return False

            return distance[py, px] != nodata

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            linestring = [point for point in feature.geometry().asPolyline()]

            for a, b in zip(linestring[:-1], linestring[1:]):

                segments.append((a.x(), a.y(), b.x(), b.y()))
                midpoints.append((0.5*(a.x() + b.x()), 0.5*(a.y() + b.y())))

        segments = np.array(segments)
        midpoints = np.array(midpoints)
        midpoints_index = cKDTree(midpoints, balanced_tree=True)

        feedback.setProgressText('Extract pixels within max distance')

        # query_pixels = np.array([
        #     (col, row)
        #     for row in range(height) for col in range(width)
        #     if distance[row, col] > 0 and distance[row, col] < max_distance
        # ])

        query_pixels = ta.extract_pixels_within_distance(distance, max_distance)

        feedback.pushInfo('Extracted %d pixels ...' % len(query_pixels))

        query_points = pixeltoworld(query_pixels, transform)

        def signed_distance(a, b, c):
            """
            Distance from C to segment [AB].
            a, b, c: array-like of pairs of (x, y) coordinates
            """

            segment_ab = b - a
            segment_ac = c - a
            length_ab = np.linalg.norm(segment_ab, axis=1)
            # length_ac = np.linalg.norm(segment_ac, axis=1)

            # dot = AB.AC / AB^2
            #     = |AC| * cos(AB, AC) / |AB|
            dot = np.sum(segment_ab*segment_ac, axis=1) / (length_ab**2)
            dot[dot < 0.0] = 0.0
            dot[dot > 1.0] = 1.0

            nearest = np.array([
                a[:, 0] + dot*segment_ab[:, 0],
                a[:, 1] + dot*segment_ab[:, 1]]).T

            distance = np.linalg.norm(nearest - c, axis=1)
            distance[np.isnan(distance)] = np.infty

            signed_dist = np.cross(segment_ab, segment_ac) / length_ab

            return distance, signed_dist, dot

        fillval = -999
        out = np.zeros_like(distance)

        # ta.side_of_nearest_segment(query_pixels, np.float32(query_points), np.float32(segments), out, feedback)

        # total = 100.0 / query_pixels.shape[0] if query_pixels.shape[0] else 0

        # for current in range(query_pixels.shape[0]):

        #     row, col = query_pixels[current]
        #     x, y = query_points[current]

        #     # TODO use index or quadtree

        #     point = np.array([(x, y)])
        #     dist, signed_dist, pos = signed_distance(segments[:, :2], segments[:, 2:], point)

        #     min_dist = float('inf')
        #     min_signed = float('inf')
        #     nearest = 0

        #     for k in range(len(dist)):

        #         if dist[k] < min_dist:

        #             min_dist = dist[k]
        #             min_signed = signed_dist[k]
        #             nearest = k

        #         elif dist[k] == min_dist and abs(signed_dist[k]) < abs(min_signed):

        #             min_signed = signed_dist[k]
        #             nearest = k

        #     out[row, col] = np.sign(min_signed)
        #     # out[row, col] = min_dist

        #     feedback.setProgress(int(current*total))

        # query_points_index = cKDTree(query_points, balanced_tree=True)

        feedback.setProgressText('Query index')

        nearest_dist, nearest_idx = midpoints_index.query(query_points, k=5)

        feedback.setProgressText('Calculate distance to nearest segment')

        for current in range(query_pixels.shape[0]):

            row, col = query_pixels[current]
            x, y = query_points[current]

            point = np.array([(x, y)])
            nearest_segments = np.take(segments, nearest_idx[current], axis=0, mode='wrap')
            dist, signed_dist, pos = ta.signed_distance(nearest_segments[:, :2], nearest_segments[:, 2:], point)

            min_dist = float('inf')
            min_signed = float('inf')
            # nearest = 0

            for k in range(len(dist)):

                if dist[k] < min_dist:

                    min_dist = dist[k]
                    min_signed = signed_dist[k]
                    # nearest = k

                elif dist[k] == min_dist and abs(signed_dist[k]) < abs(min_signed):

                    min_signed = signed_dist[k]
                    # nearest = k

            out[row, col] = np.sign(min_signed)
            # out[row, col] = min_dist

            feedback.setProgress(int(current*total))

        feedback.setProgressText('Propagate values')

        data = np.float32(distance == 0)
        data[distance == nodata] = -1
        out[distance > max_distance] = fillval
        ta.shortest_ref(data, -1, startval=1, fillval=fillval, out=out, feedback=feedback)

        out = out * distance
        out[distance == nodata] = nodata

        feedback.setProgress(100)
        feedback.setProgressText(self.tr('Write output ...'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=distance_ds.RasterXSize,
            ysize=distance_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(distance_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(distance_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources
        distance_ds = None
        dst = None

        return {self.OUTPUT: output}
