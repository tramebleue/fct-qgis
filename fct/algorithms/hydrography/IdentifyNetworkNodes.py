# -*- coding: utf-8 -*-

"""
IdentifyNetworkNodes - Identify nodes in hydrogaphy network

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
    QgsProcessingParameterNumber,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def simple_linestring_op(operation):
    """ Apply geometry operation on polyline
        or, in case of a multi-polyline, on each part
    """

    def wrapper(geom, *args, **kwargs): #pylint: disable=missing-docstring

        if geom.isMultipart():

            for polyline in geom.asMultiPolyline():
                operation(polyline, *args, **kwargs)

        else:

            polyline = geom.asPolyline()
            operation(polyline, *args, **kwargs)

    return wrapper

class IdentifyNetworkNodes(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Identify nodes in hydrogaphy network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'IdentifyNetworkNodes')

    INPUT = 'INPUT'
    QUANTIZATION = 'QUANTIZATION'
    OUTPUT = 'OUTPUT'
    NODES = 'NODES'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input linestrings'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterNumber(
            self.QUANTIZATION,
            self.tr('Quantization Factor for Node Coordinates'),
            minValue=0.0,
            defaultValue=1e8))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Lines With Identified Nodes'),
            QgsProcessing.TypeVectorLine))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.NODES,
            self.tr('Nodes'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)

        # Step 1
        feedback.setProgressText(self.tr("[1/4] Get Line Endpoints ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        coordinates = list()

        @simple_linestring_op
        def extract_coordinates(polyline):
            """ Extract endpoints coordinates
            """

            a = polyline[0]
            b = polyline[-1]
            coordinates.append(tuple(a))
            coordinates.append(tuple(b))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            extract_coordinates(feature.geometry())
            feedback.setProgress(int(total * current))

        # Step 2
        feedback.setProgressText(self.tr("[2/4] Quantize coordinates ..."))

        coordinates = np.array(coordinates)
        minx = np.min(coordinates[:, 0])
        miny = np.min(coordinates[:, 1])
        maxx = np.max(coordinates[:, 0])
        maxy = np.max(coordinates[:, 1])

        quantization = 1e8
        kx = (minx == maxx) and 1 or (maxx - minx)
        ky = (miny == maxy) and 1 or (maxy - miny)
        sx = kx / quantization
        sy = ky / quantization

        coordinates = np.int32(np.round((coordinates - (minx, miny)) / (sx, sy)))

        # Step 3
        feedback.setProgressText(self.tr("[3/4] Build Endpoints Index ..."))

        fields = QgsFields()
        fields.append(QgsField('GID', type=QVariant.Int, len=10))

        (sink, nodes_id) = self.parameterAsSink(
            parameters,
            self.NODES,
            context,
            fields,
            QgsWkbTypes.Point,
            layer.sourceCrs())

        point_index = QgsSpatialIndex()
        # point_list = list()
        coordinates_map = dict()
        gid = 0

        total = 100.0 / len(coordinates)

        for i, coordinate in enumerate(coordinates):

            if feedback.isCanceled():
                break

            c = tuple(coordinate)

            if c not in coordinates_map:

                coordinates_map[c] = i
                # point_list.append(c)

                geometry = QgsGeometry.fromPointXY(QgsPointXY(c[0]*sx + minx, c[1]*sy + miny))
                point_feature = QgsFeature()
                point_feature.setId(gid)
                point_feature.setAttributes([gid])
                point_feature.setGeometry(geometry)

                point_index.addFeature(point_feature)
                sink.addFeature(point_feature)

                gid = gid + 1

            feedback.setProgress(int(total * i))

        del coordinates
        del coordinates_map

        # Step 4
        feedback.setProgressText(self.tr("[4/4] Output Lines with Node Attributes ..."))

        fields = QgsFields(layer.fields())
        fields.append(QgsField('NODEA', QVariant.Int, len=10))
        fields.append(QgsField('NODEB', QVariant.Int, len=10))

        (sink, output_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        def nearest(point):
            """ Return the nearest point in the point index
            """

            for candidate in point_index.nearestNeighbor(point, 1):
                return candidate

            return None

        @simple_linestring_op
        def output_simple_features(polyline, feature):
            """ Split multi-polylines into simple polyline if required,
                match endpoints into the node index,
                and output one or more stream features with node attributes
            """

            a = polyline[0]
            b = polyline[-1]
            simple_geom = QgsGeometry.fromPolylineXY(polyline)

            out_feature = QgsFeature()
            out_feature.setGeometry(simple_geom)
            out_feature.setAttributes(feature.attributes() + [
                nearest(a),
                nearest(b)
            ])

            sink.addFeature(out_feature)

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            geom = feature.geometry()

            if not geom.isMultipart():

                polyline = geom.asPolyline()
                a = polyline[0]
                b = polyline[-1]

                out_feature = QgsFeature()
                out_feature.setGeometry(geom)
                out_feature.setAttributes(feature.attributes() + [
                    nearest(a),
                    nearest(b)
                ])

                sink.addFeature(out_feature)

            else:
                output_simple_features(geom, feature)

            feedback.setProgress(int(total * current))

        return {
            self.OUTPUT: output_id,
            self.NODES: nodes_id
        }
