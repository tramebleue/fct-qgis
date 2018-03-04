# -*- coding: utf-8 -*-

"""
***************************************************************************
    NodesFromEdges.py
    ---------------------
    Date                 : February 2018
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

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

class NodesFromEdges(GeoAlgorithm):

    EDGE_LAYER = 'EDGE_LAYER'
    NODE_A_FIELD = 'NODE_A_FIELD'
    NODE_B_FIELD = 'NODE_B_FIELD'

    ATTRIBUTE_LAYER = 'ATTRIBUTE_LAYER'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Nodes From Edges')
        self.group, self.i18n_group = self.trAlgorithm('Graph Routines')

        self.addParameter(ParameterVector(self.EDGE_LAYER,
                                          self.tr('Edge Layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        self.addParameter(ParameterTableField(self.NODE_A_FIELD,
                                          self.tr('Node A Field'),
                                          parent=self.EDGE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.NODE_B_FIELD,
                                          self.tr('Node B Field'),
                                          parent=self.EDGE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.ATTRIBUTE_LAYER,
                                          self.tr('Attribute Layer'), [ParameterVector.VECTOR_TYPE_POINT],
                                          optional=True))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Nodes')))

    def processAlgorithm(self, progress):

        seen_nodes = set()

        edge_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.EDGE_LAYER))
        node_a_field = self.getParameterValue(self.NODE_A_FIELD)
        node_b_field = self.getParameterValue(self.NODE_B_FIELD)
        attribute_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.ATTRIBUTE_LAYER))
        
        fields = [
                QgsField('NODE_ID', QVariant.Int, len=10)
            ]

        if attribute_layer is not None:
            attribute_index = QgsSpatialIndex(attribute_layer.getFeatures())
            fields = fields + attribute_layer.fields().toList()

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields,
            QGis.WKBPoint,
            edge_layer.crs())
        
        total = 100.0 / edge_layer.featureCount()

        for current, edge in enumerate(edge_layer.getFeatures()):

            a = edge.attribute(node_a_field)
            b = edge.attribute(node_b_field)
            line = edge.geometry().asPolyline()
            endpoints = [ QgsGeometry.fromPoint(line[x]) for x in (0, -1) ]

            for node, point in zip([ a, b ], endpoints):

                if not node in seen_nodes:

                    if attribute_layer is not None:

                        for c in attribute_index.nearestNeighbor(point.asPoint(), 1):
                            match = attribute_layer.getFeatures(QgsFeatureRequest(c)).next()
                            attributes = [ node ] + match.attributes()

                    else:

                        attributes = [ node ]

                    out_node = QgsFeature()
                    out_node.setAttributes(attributes)
                    out_node.setGeometry(point)
                    writer.addFeature(out_node)
                    seen_nodes.add(node)

            progress.setPercentage(int(current * total))