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

from ...core import IdGenerator

class DensifyNetworkNodes(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    MEASURE_FIELD = 'MEASURE_FIELD'
    MAX_DISTANCE = 'MAX_DISTANCE'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Densify Network Nodes')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        self.addParameter(ParameterTableField(self.FROM_NODE_FIELD,
                                          self.tr('From Node Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        
        self.addParameter(ParameterTableField(self.TO_NODE_FIELD,
                                          self.tr('To Node Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                          self.tr('Measure Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterNumber(self.MAX_DISTANCE,
                                          self.tr('Max Distance'),
                                          minValue=0.0, default=50.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Densified Network')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)
        measure_field = self.getParameterValue(self.MEASURE_FIELD)
        max_distance = self.getParameterValue(self.MAX_DISTANCE)

        from_node_field_idx = vector.resolveFieldIndex(layer, from_node_field)
        to_node_field_idx = vector.resolveFieldIndex(layer, to_node_field)
        meas_field_idx = vector.resolveFieldIndex(layer, measure_field)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList(),
            layer.dataProvider().geometryType(),
            layer.crs())

        total = 100.0 / layer.featureCount()
        max_id = 0

        progress.setText(self.tr('Find Max Node ID ...'))

        for current, feature in enumerate(layer.getFeatures()):

            fid = feature.attribute(from_node_field)
            if fid > max_id:
                max_id = fid
            fid = feature.attribute(to_node_field)
            if fid > max_id:
                max_id = fid
            
            progress.setPercentage(int(current * total))

        node_id = IdGenerator(max_id)

        def densify(feature, startpos, length, k, startid, endid, meas):

            half1 = [ startpos + 0.5*length - (i+0.5)*max_distance for i in range(0, k // 2) ]
            half1.reverse()
            half2 = [ startpos + 0.5*length + (i+0.5)*max_distance for i in range(0, k // 2) ]

            a = feature.geometry().interpolate(startpos).asPoint()
            aid = startid

            for pos in half1 + half2:

                b = feature.geometry().interpolate(pos).asPoint()
                bid = next(node_id)
                segment = QgsGeometry.fromPolyline([ a, b ])

                out_feature = QgsFeature()
                out_feature.setGeometry(segment)
                attrs = feature.attributes()
                attrs[from_node_field_idx] = aid
                attrs[to_node_field_idx] = bid
                attrs[meas_field_idx] = meas - pos
                out_feature.setAttributes(attrs)

                writer.addFeature(out_feature)

                a = b
                aid = bid

            pos = startpos + length
            b = feature.geometry().interpolate(pos).asPoint()
            bid = endid
            segment = QgsGeometry.fromPolyline([ a, b ])

            out_feature = QgsFeature()
            out_feature.setGeometry(segment)
            attrs = feature.attributes()
            attrs[from_node_field_idx] = aid
            attrs[to_node_field_idx] = bid
            attrs[meas_field_idx] = meas - pos
            out_feature.setAttributes(attrs)
            
            writer.addFeature(out_feature)

        progress.setText(self.tr('Densify ...'))

        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):

            length = feature.geometry().length()
            k = int(length // max_distance)
            aid = feature.attribute(from_node_field)
            bid = feature.attribute(to_node_field)
            meas = feature.attribute(measure_field) + length

            if (k - 1) % 2 == 0:

                densify(feature, 0.0, length, k - 1, aid, bid, meas)

            else:

                k = (k - 2) // 2
                midpoint_id = next(node_id)
                densify(feature, 0.0, 0.5*length, k, aid, midpoint_id, meas)
                densify(feature, 0.5*length, 0.5*length, k, midpoint_id, bid, meas)

            progress.setPercentage(int(current * total))