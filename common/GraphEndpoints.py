# -*- coding: utf-8 -*-

"""
***************************************************************************
    GraphEndpoints.py
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

class GraphEndpoints(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Graph Endpoints')
        self.group, self.i18n_group = self.trAlgorithm('Graph Routines')

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

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Graph Endpoints')))

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
        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            if node_index.has_key(from_node):
                node_index[from_node].append(to_node)
            else:
                node_index[from_node] = [ to_node ]
                polyline = self.asPolyline(feature.geometry())
                writeEndpoint(from_node, polyline[0])

            if not node_index.has_key(to_node):
                node_index[to_node] = list()
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

        progress.setText(self.tr("Output endpoints ..."))

        # outlayer = dataobjects.getObjectFromUri(self.getOutputFromName(self.OUTPUT_LAYER).value)
        # outlayer = self.getOutputFromName(self.OUTPUT_LAYER).layer
        # outlayer.startEditing()
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            outlayer.fields().toList(),
            outlayer.dataProvider().geometryType(),
            outlayer.crs())
        total = 100.0 / outlayer.featureCount()
        
        for current, feature in enumerate(outlayer.getFeatures()):

            gid = feature.attribute('GID')
            din = in_degree[gid]
            dout = len(node_index[gid])
            feature.setAttributes([
                    gid,
                    din,
                    dout,
                    self.node_type(din, dout)
                ])
            writer.addFeature(feature)

            progress.setPercentage(int(current * total))

        outlayer.commitChanges()