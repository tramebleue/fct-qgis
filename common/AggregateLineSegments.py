# -*- coding: utf-8 -*-

"""
***************************************************************************
    AggregateLineSegments.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

class AggregateLineSegments(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Aggregate Line Segments')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterTableField(self.FROM_NODE_FIELD,
                                          self.tr('From Node Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        self.addParameter(ParameterTableField(self.TO_NODE_FIELD,
                                          self.tr('To Node Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Aggregated Lines')))

    def node_type(self, in_degree, out_degree):

        if in_degree == 0:
            if out_degree == 0:
                return 'XOUT' # Exterior node (not included in graph construction)
            elif out_degree == 1:
                return 'SRCE' # Source node
            else:
                return 'DIVG' # Diverging node
        elif in_degree == 1:
            if out_degree == 0:
                return 'EXUT' # Outlet (exutoire)
            elif out_degree == 1:
                return 'NODE' # Simple node between 2 edges (reaches)
            else:
                return 'DIFL' # Diffluence
        else:
            if out_degree == 0:
                return 'XSIN' # Sink
            elif out_degree == 1:
                return 'CONF' # Confluence
            else:
                return 'XXOS' # Crossing

    def asPolyline(self, geometry):

        if geometry.isMultipart():
            return geometry.asMultiPolyline()[0]
        else:
            return geometry.asPolyline()

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)

        progress.setText(self.tr("Build node index ..."))

        fields = [
                QgsField('GID', type=QVariant.Int, len=10),
                QgsField('DIN', type=QVariant.Int, len=6),
                QgsField('DOUT', type=QVariant.Int, len=6),
                QgsField('TYPE', type=QVariant.String, len=4)
            ]
        
        outlayer = QgsVectorLayer('Point', 'endpoints', 'memory')
        outlayer.setCrs(layer.crs())
        outlayer.dataProvider().addAttributes(fields)
        outlayer.startEditing()

        def writeEndpoint(gid, point):

            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPoint(point))
            f.setAttributes([
                    gid,
                    0,
                    0,
                    'XOUT'
                ])
            outlayer.addFeature(f)

        node_index = dict()
        feature_index = dict()
        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            if node_index.has_key(from_node):
                node_index[from_node].append(to_node)
                feature_index[from_node].append(feature.id())
            else:
                node_index[from_node] = [ to_node ]
                feature_index[from_node] = [ feature.id() ]
                polyline = self.asPolyline(feature.geometry())
                writeEndpoint(from_node, polyline[0])

            if not node_index.has_key(to_node):
                node_index[to_node] = list()
                feature_index[to_node] = list()
                polyline = self.asPolyline(feature.geometry())
                writeEndpoint(to_node, polyline[-1])

            progress.setPercentage(int(current * total))

        outlayer.commitChanges()

        progress.setText(self.tr("Compute in-degree ..."))

        in_degree = dict()
        for node in node_index.keys():
            if not in_degree.has_key(node):
                in_degree[node] = 0
            for to_node in node_index[node]:
                in_degree[to_node] = in_degree.get(to_node, 0) + 1

        progress.setText(self.tr("Aggregate lines ..."))

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            [
                QgsField('GID', type=QVariant.Int, len=10),
                QgsField(from_node_field, type=QVariant.Int, len=10),
                QgsField(to_node_field, type=QVariant.Int, len=10)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())
        
        total = 100.0 / layer.featureCount()

        process_stack = list()

        for node in node_index.keys():
            if len(node_index[node]) >= 1 and in_degree[node] == 0:
                process_stack.append(node)
        
        current = 0
        fid = 0
        seen_nodes = set()

        while process_stack:

            from_node = process_stack.pop()
            seen_nodes.add(from_node)
            # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Processing node %d" % from_node)

            for branch in range(0, len(node_index[from_node])):

                next_node = node_index[from_node][branch]
                next_segment_id = feature_index[from_node][branch]
                segment = layer.getFeatures(QgsFeatureRequest(next_segment_id)).next()
                vertices = self.asPolyline(segment.geometry())

                current = current + 1
                progress.setPercentage(int(current * total))

                while len(node_index[next_node]) == 1 and in_degree[next_node] == 1:

                        next_segment_id = feature_index[next_node][0]
                        segment = layer.getFeatures(QgsFeatureRequest(next_segment_id)).next()
                        vertices = vertices[:-1] + self.asPolyline(segment.geometry())

                        current = current + 1
                        progress.setPercentage(int(current * total))

                        next_node = node_index[next_node][0]
                    
                feature = QgsFeature()
                feature.setGeometry(QgsGeometry.fromPolyline(vertices))
                feature.setAttributes([
                        fid,
                        from_node,
                        next_node
                    ])
                writer.addFeature(feature)
                fid = fid + 1

                # dont't process twice or more after confluences
                # if branch == 0:
                if not next_node in seen_nodes:
                    process_stack.append(next_node)

                    

        ProcessingLog.addToLog(
            ProcessingLog.LOG_INFO,
            "Created %d line features" % fid)