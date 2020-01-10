# -*- coding: utf-8 -*-

"""
Stream To Feature

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from heapq import heapify, heappop
from collections import namedtuple, defaultdict

import numpy as np
from osgeo import gdal

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

# from processing.core.ProcessingConfig import ProcessingConfig
from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

Pixel = namedtuple('Pixel', ('area', 'i', 'j'))
Outlet = namedtuple('Outlet', ('fid', 'x', 'y'))

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

class SubGridTopography(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Find downstream feature using subgrid topography algorithm
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SubGridTopography')

    INPUT = 'INPUT'
    FLOW = 'FLOW'
    FLOW_ACC = 'FLOW_ACC'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Grid'),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW_ACC,
            self.tr('Flow Accumulation')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('SubGrid Nodes'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        flow_acc_lyr = self.parameterAsRasterLayer(parameters, self.FLOW_ACC, context)

        flow_ds = gdal.OpenEx(flow_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        flow_acc_ds = gdal.OpenEx(flow_acc_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        flow_acc = flow_acc_ds.GetRasterBand(1).ReadAsArray()

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('OX', QVariant.Double), fields)
        appendUniqueField(QgsField('OY', QVariant.Double), fields)
        appendUniqueField(QgsField('NX', QVariant.Double), fields)
        appendUniqueField(QgsField('NY', QVariant.Double), fields)
        appendUniqueField(QgsField('LINKID', QVariant.Int), fields)
        appendUniqueField(QgsField('LINKX', QVariant.Double), fields)
        appendUniqueField(QgsField('LINKY', QVariant.Double), fields)
        appendUniqueField(QgsField('DRAINAGE', QVariant.Double), fields)
        appendUniqueField(QgsField('LOCALCA', QVariant.Double), fields)
        appendUniqueField(QgsField('CONTRIB', QVariant.Double), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.Point,
            layer.sourceCrs())

        transform = flow_ds.GetGeoTransform()
        # resolution_x = transform[1]
        # resolution_y = -transform[5]

        height, width = flow.shape

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0
        mask = np.zeros_like(flow, dtype=np.bool)

        ci = [-1, -1,  0,  1,  1,  1,  0, -1]
        cj = [ 0,  1,  1,  1,  0, -1, -1, -1]
        upward = [16,  32,  64,  128,  1,  2,  4,  8]
        nodata = -1
        noflow = 0

        def isdata(i, j):
            """
            True if (py, px) is a valid pixel coordinate
            """

            return j >= 0 and i >= 0 and j < width and i < height

        def local_contributive_area(i0, j0):
            
            queue = [(i0, j0)]
            lca = 0
            # length = dict()

            while queue:

                i, j = queue.pop()

                for x in range(8):

                    ix =  i + ci[x]
                    jx =  j + cj[x]

                    if isdata(ix, jx) and mask[ix, jx] and flow[ix, jx] == upward[x] :

                        lca += 1
                        # length[(ix, jx)] = length[(i, j)] + 1
                        queue.append((ix, jx))

            return lca

        feedback.setProgressText(self.tr("Find feature outlets ..."))

        outlet_pixels = dict()
        centroids = dict()

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            geom = feature.geometry()
            centroids[feature.id()] = geom.centroid().asPoint()
            bbox = geom.boundingBox()
            (jmin, imin), (jmax, imax) = worldtopixel(np.array([(bbox.xMinimum(), bbox.yMaximum()), (bbox.xMaximum(), bbox.yMinimum())]), transform)

            # mask = np.zeros((imax-imin+1, jmax-jmin+1), dtype=np.bool)
            mask[:, :] = False
            max_acc = list()

            for i in range(imin, imax+1):
                for j in range(jmin, jmax+1):
                    # test if pixel is in geometry
                    px, py = pixeltoworld(np.array([j, i]), transform)
                    if isdata(i, j) and flow[i, j] != nodata and geom.contains(QgsGeometry.fromPointXY(QgsPointXY(px, py))):
                        # mask[i-imin, j-jmin] = True
                        mask[i, j] = True
                        acc = flow_acc[i, j]
                        max_acc.append(Pixel(-acc, i, j))

            if len(max_acc) == 0:
                continue

            # sort by acc
            heapify(max_acc)

            candidate = heappop(max_acc)
            local_acc = local_contributive_area(candidate.i, candidate.j)

            # TODO test if next candidate has greater local_acc
            while max_acc:

                next_candidate = heappop(max_acc)
                next_local_acc = local_contributive_area(next_candidate.i, next_candidate.j)

                if next_local_acc > local_acc:

                    candidate = next_candidate
                    local_acc = next_local_acc

                else:

                    break

            outlet_pixels[feature.id()] = Pixel(local_acc, candidate.i, candidate.j)

        feedback.setProgressText(self.tr("Build upstream/downstream graph ..."))

        # pixel to feature map
        pixels = {(c.i, c.j): fid for fid, c in outlet_pixels.items()}
        # graph: feature A --(outlet xb, yb)--> feature B
        graph = dict()

        # for current, feature in enumerate(layer.getFeatures()):
        for current, fid in enumerate(outlet_pixels):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            outlet = outlet_pixels[fid]
            i = outlet.i
            j = outlet.j

            while isdata(i, j):

                direction = flow[i, j]
                if direction == nodata or direction == noflow:
                    break

                x = int(np.log2(direction))

                i = i + ci[x]
                j = j + cj[x]

                if (i, j) in pixels:

                    ide = pixels[(i, j)]
                    xe, ye = pixeltoworld(np.array([j, i]), transform)
                    graph[fid] = Outlet(ide, float(xe), float(ye))
                    break

        feedback.setProgressText(self.tr("Output subgrid graph ..."))

        reverse_graph = defaultdict(list)
        for a, b in graph.items():
            reverse_graph[b.fid].append(a)

        for current, feature in enumerate(layer.getFeatures()):

            fid = feature.id()
            if fid not in outlet_pixels:
                continue

            origin = feature.geometry().centroid().asPoint()
            target = graph.get(feature.id(), None)

            if target is not None:
                target_fid = target.fid
                neighbor = centroids[target_fid]
                xe = target.x
                ye = target.y
            else:
                target_fid = None
                neighbor = None
                xe = ye = None

            outlet = outlet_pixels[fid]
            i = outlet.i
            j = outlet.j
            outlet_area = float(flow_acc[i, j])
            xo, yo = pixeltoworld(np.array([j, i]), transform)
            local_contributive_area = outlet.area

            upstream_area = 0.0
            for a in reverse_graph[fid]:
                if a in outlet_pixels:
                    a_outlet = outlet_pixels[a]
                    a_area = float(flow_acc[a_outlet.i, a_outlet.j])
                    upstream_area += a_area

            contributive_area = outlet_area - upstream_area

            out_feature = QgsFeature()
            out_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(xo, yo)))
            out_feature.setAttributes(feature.attributes() + [
                origin.x(),
                origin.y(),
                neighbor.x() if neighbor is not None else None,
                neighbor.y() if neighbor is not None else None,
                target_fid,
                xe,
                ye,
                outlet_area,
                local_contributive_area,
                contributive_area
            ])

            sink.addFeature(out_feature)

        # Properly close GDAL resources
        flow_ds = None
        flow_acc_ds = None

        return {
            self.OUTPUT: dest_id
        }
