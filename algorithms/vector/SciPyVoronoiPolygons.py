# -*- coding: utf-8 -*-

"""
SciPyVoronoiPolygons - Generates Voronoi polygons based on SciPy Voronoi implementation

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict
import numpy as np

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def voronoi_polygons(voronoi, diameter): # pylint: disable=too-many-locals
    """Generate shapely.geometry.Polygon objects corresponding to the
    regions of a scipy.spatial.Voronoi object, in the order of the
    input points. The polygons for the infinite regions are large
    enough that all points within a distance 'diameter' of a Voronoi
    vertex are contained in one of the infinite polygons.

    See
    https://stackoverflow.com/questions/23901943/voronoi-compute-exact-boundaries-of-every-region/52727406#52727406
    """

    # pylint: disable=invalid-name,

    centroid = voronoi.points.mean(axis=0)

    # Mapping from (input point index, Voronoi point index) to list of
    # unit vectors in the directions of the infinite ridges starting
    # at the Voronoi point and neighbouring the input point.
    ridge_direction = defaultdict(list)

    for (p, q), rv in zip(voronoi.ridge_points, voronoi.ridge_vertices):

        u, v = sorted(rv)

        if u == -1:
            # Infinite ridge starting at ridge point with index v,
            # equidistant from input points with indexes p and q.
            t = voronoi.points[q] - voronoi.points[p] # tangent
            n = np.array([-t[1], t[0]]) / np.linalg.norm(t) # normal
            midpoint = voronoi.points[[p, q]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - centroid, n)) * n
            ridge_direction[p, v].append(direction)
            ridge_direction[q, v].append(direction)

    for i, r in enumerate(voronoi.point_region):

        region = voronoi.regions[r]
        if -1 not in region:
            # Finite region.
            yield i, QgsGeometry.fromPolygonXY([[
                QgsPointXY(x, y) for x, y
                in voronoi.vertices[region]]])
            continue

        # Infinite region.
        inf = region.index(-1)              # Index of vertex at infinity.
        j = region[(inf - 1) % len(region)] # Index of previous vertex.
        k = region[(inf + 1) % len(region)] # Index of next vertex.

        try:
            if j == k:
                # Region has one Voronoi vertex with two ridges.
                dir_j, dir_k = ridge_direction[i, j]
            else:
                # Region has two Voronoi vertices, each with one ridge.
                dir_j, = ridge_direction[i, j]
                dir_k, = ridge_direction[i, k]
        except ValueError:
            continue

        # Length of ridges needed for the extra edge to lie at least
        # 'diameter' away from all Voronoi vertices.
        length = 2 * diameter / np.linalg.norm(dir_j + dir_k)

        # Polygon consists of finite part plus an extra edge.
        finite_part = voronoi.vertices[region[inf + 1:] + region[:inf]]
        extra_edge = [voronoi.vertices[j] + dir_j * length,
                      voronoi.vertices[k] + dir_k * length]

        yield i, QgsGeometry.fromPolygonXY([[
            QgsPointXY(x, y) for x, y
            in np.concatenate((finite_part, extra_edge))]])

class SciPyVoronoiPolygons(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ This algorithm takes a points layer
        and generates a polygon layer containing the voronoi polygons
        corresponding to those input points.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SciPyVoronoiPolygons')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            from scipy.spatial import Voronoi
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.spatial')

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input Points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Voronoi Polygons'),
            QgsProcessing.TypeVectorPolygon))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from scipy.spatial import Voronoi #pylint: disable=no-name-in-module

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            layer.fields(),
            QgsWkbTypes.Polygon,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        points = list()

        extent = layer.extent()
        diameter = np.linalg.norm(np.array([
            [p.x(), p.y()] for p
            in QgsGeometry.fromRect(extent).asPolygon()[0]]).ptp(axis=0))

        feedback.setProgressText(self.tr('Read input points'))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            if feature.geometry():
                points.append((feature.id(), feature.geometry().asPoint()))

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr('Compute Voronoi polygons'))

        voronoi = Voronoi(np.array([[p.x(), p.y()] for i, p in points]))

        feedback.setProgressText(self.tr('Output polygons'))

        for current, (index, polygon) in enumerate(voronoi_polygons(voronoi, diameter)):

            if feedback.isCanceled():
                break

            if polygon.isGeosValid():

                point = layer.getFeature(points[index][0])

                feature = QgsFeature()
                feature.setGeometry(polygon)
                feature.setAttributes(point.attributes())
                sink.addFeature(feature)

            else:

                print(polygon.asWkt())

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
