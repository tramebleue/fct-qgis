# -*- coding: utf-8 -*-

"""
***************************************************************************
    DirectedGraphFromUndirected.py
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

def swap(a, b):

    return b, a

class DirectedGraphFromUndirected(GeoAlgorithm):

    EDGE_LAYER = 'EDGE_LAYER'
    NODE_A_FIELD = 'NODE_A_FIELD'
    NODE_B_FIELD = 'NODE_B_FIELD'

    # ATTRIBUTE_LAYER = 'ATTRIBUTE_LAYER'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Directed Graph From Undirected Graph')
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

        # self.addParameter(ParameterVector(self.ATTRIBUTE_LAYER,
        #                                   self.tr('Attribute Layer'), [ParameterVector.VECTOR_TYPE_POINT],
        #                                   optional=True))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Directed Graph')))

    def processAlgorithm(self, progress):


        edge_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.EDGE_LAYER))
        node_a_field = self.getParameterValue(self.NODE_A_FIELD)
        node_b_field = self.getParameterValue(self.NODE_B_FIELD)
        # attribute_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.ATTRIBUTE_LAYER))
        
        fields = [
                QgsField('EDGE_ID', QVariant.Int, len=10)
            ] + edge_layer.fields().toList()

        # if attribute_layer is not None:
        #     attribute_index = QgsSpatialIndex(attribute_layer.getFeatures())
        #     fields = fields + attribute_layer.fields().toList()

        writer = writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields,
            edge_layer.dataProvider().geometryType(),
            edge_layer.crs())
        
        total = 100.0 / edge_layer.featureCount()
        fid = 0

        qfields = QgsFields()
        for field in fields:
            qfields.append(field)

        for current, edge in enumerate(edge_layer.getFeatures()):

            a = edge.attribute(node_a_field)
            b = edge.attribute(node_b_field)
            line = edge.geometry().asPolyline()

            for i in range(0,2):

                outfeature = QgsFeature(qfields)
                outfeature.setAttributes([ fid ] + edge.attributes())
                outfeature.setAttribute(node_a_field, a)
                outfeature.setAttribute(node_b_field, b)
                outfeature.setGeometry(QgsGeometry.fromPolyline(line))
                writer.addFeature(outfeature)

                a, b = swap(a, b)
                line.reverse()
                fid = fid + 1

            progress.setPercentage(int(current * total))