# -*- coding: utf-8 -*-

"""
***************************************************************************
    Sequencing2.py
    ---------------------
    Date                 : November 2016
    Copyright            : (C) 2016 by Christophe Rousson
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Christophe Rousson'
__date__ = 'November 2016'
__copyright__ = '(C) 2016, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFeatureRequest, QgsFields, QgsField
from qgis.core import QgsVectorLayer
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from ...core import vector as vector_helper
import numpy as np

def linestring_op(op):

    def wrapper(geom, *args, **kwargs):

        if geom.isMultipart():

            for polyline in geom.asMultiPolyline():
                op(polyline, *args, **kwargs)

        else:

            polyline = geom.asPolyline()
            op(polyline, *args, **kwargs)

    return wrapper

class IdentifyNetworkNodes(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    # SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    
    OUTPUT_LAYER = 'OUTPUT'
    # ENDPOINTS_LAYER = 'ENDPOINTS_LAYER'
    # UNMATCHED_LAYER = 'UNMATCHED_LAYER'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Identify Network Nodes')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        # self.addParameter(ParameterNumber(self.SEARCH_DISTANCE,
        #                                   self.tr('Search Distance'), default=10.0, optional=False))
        
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Lines With Identified Nodes')))

    def processAlgorithm(self, progress):

        input_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))

        # Step 1
        progress.setText(self.tr("Get Line Endpoints ..."))

        features = vector.features(input_layer)
        total = 100.0 / len(features)
        coordinates = list()

        @linestring_op
        def extract_coordinates(polyline):

            a = polyline[0]
            b = polyline[-1]
            coordinates.append(tuple(a))
            coordinates.append(tuple(b))

        for current, feature in enumerate(features):

            progress.setPercentage(int(total * current))

            geom = feature.geometry()
            extract_coordinates(geom)

            # if geom.isMultipart():

            #     for polyline in geom.asMultiPolyline():
            #         a = polyline[0]
            #         b = polyline[-1]
            #         coordinates.append(tuple(a))
            #         coordinates.append(tuple(b))

            # else:
            
            #     polyline = geom.asPolyline()
            #     a = polyline[0]
            #     b = polyline[-1]
            #     coordinates.append(tuple(a))
            #     coordinates.append(tuple(b))

        # Step 2
        progress.setText(self.tr("Quantize coordinates ..."))

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
        progress.setText(self.tr("Build Endpoints Index ..."))

        coordinates_map = dict()
        point_layer = QgsVectorLayer("Point", "endpoints", "memory")
        point_layer.setCrs(input_layer.crs())
        point_layer.dataProvider().addAttributes([
                QgsField('GID', type=QVariant.Int, len=10)
            ])

        point_layer.startEditing()
        gid = 0

        total = 100.0 / len(coordinates)
        for i in xrange(len(coordinates)):

            progress.setPercentage(int(total * i))
            c = tuple(coordinates[i])

            if not coordinates_map.has_key(c):
                coordinates_map[c] = i
                geometry = QgsGeometry.fromPoint(QgsPoint(c[0]*sx + minx, c[1]*sy + miny))
                point_feature = QgsFeature()
                point_feature.setAttributes([ gid ])
                point_feature.setGeometry(geometry)
                point_layer.addFeature(point_feature)
                gid = gid + 1

        del coordinates_map
        point_layer.commitChanges()
        point_index = QgsSpatialIndex(point_layer.getFeatures())

        # Step 4
        progress.setText(self.tr("Output Lines with Node Attributes ..."))

        features = vector.features(input_layer)
        total = 100.0 / len(features)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                input_layer,
                QgsField('NODE_A', QVariant.Int, len=10),
                QgsField('NODE_B', QVariant.Int, len=10)
            ),
            input_layer.dataProvider().geometryType(),
            input_layer.crs())

        def nearest(p):

            for candidate in point_index.nearestNeighbor(p, 1):

                point_feature = point_layer.getFeatures(QgsFeatureRequest(candidate)).next()
                return point_feature.attribute('GID')

            return None

        @linestring_op
        def output_node_attributes(polyline, feature):

            a = polyline[0]
            b = polyline[-1]
            simple_geom = QgsGeometry.fromPolyline(polyline)

            out_feature = QgsFeature()
            out_feature.setGeometry(simple_geom)
            out_feature.setAttributes(feature.attributes() + [
                    nearest(a),
                    nearest(b)
                ])

            writer.addFeature(out_feature)


        for current, feature in enumerate(features):

            progress.setPercentage(int(total * current))

            geom = feature.geometry()
            output_node_attributes(geom, feature)

            # if geom.isMultipart():
            #     for polyline in geom.asMultiPolyline():
                    
            #         a = polyline[0]
            #         b = polyline[-1]
            #         simple_geom = QgsGeometry.fromPolyline(polyline)

            #         out_feature = QgsFeature()
            #         out_feature.setGeometry(simple_geom)
            #         out_feature.setAttributes(feature.attributes() + [
            #                 nearest(a),
            #                 nearest(b)
            #             ])

            #         writer.addFeature(out_feature)
            # else:
                
            #     polyline = geom.asPolyline()
            #     a = polyline[0]
            #     b = polyline[-1]

            #     out_feature = QgsFeature()
            #     out_feature.setGeometry(geom)
            #     out_feature.setAttributes(feature.attributes() + [
            #             nearest(a),
            #             nearest(b)
            #         ])

            #     writer.addFeature(out_feature)

        progress.setText(self.tr('Done'))
        progress.setPercentage(100)



