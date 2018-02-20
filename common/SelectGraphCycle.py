# -*- coding: utf-8 -*-

"""
***************************************************************************
    SelectGraphCycle.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField
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

class NodeData(object):

    def __init__(self, index):
        self.index = index
        self.lowlink = index


class SelectGraphCycle(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    # OUTPUT_LAYER = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Select Graph Cycle')
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

        # self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Stream')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)

        progress.setText(self.tr("Build graph index ..."))

        node_index = dict()
        feature_index = dict()
        total = 100.0 / layer.featureCount()

        for current, feature in enumerate(layer.getFeatures()):

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            if node_index.has_key(from_node):
                node_index[from_node].append(to_node)
            else:
                node_index[from_node] = [ to_node ]

            if not node_index.has_key(to_node):
                node_index[to_node] = list()

            if feature_index.has_key((from_node, to_node)):
                feature_index[(from_node, to_node)].append(feature.id())
            else:
                feature_index[(from_node, to_node)] = [ feature.id() ]
            
            progress.setPercentage(int(current * total))

        progress.setText(self.tr("Find cycles ..."))

        stack = list()
        self.index = 0
        seen_nodes = dict()

        def connect(node):

            data = NodeData(self.index)
            seen_nodes[node] = data
            self.index = self.index + 1
            stack.append(node)

            for next_node in node_index[node]:
                if not seen_nodes.has_key(next_node):
                    connect(next_node)
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].lowlink)
                elif next_node in stack:
                    data.lowlink = min(data.lowlink, seen_nodes[next_node].index)

            if data.index == data.lowlink:

                first_back_node = stack.pop()
                
                if first_back_node != node:
                    if (first_back_node, node) in feature_index:
                        for feature_id in feature_index[(first_back_node, node)]:
                            layer.select(feature_id)
                    else:
                        ProcessingLog.addToLog(
                            ProcessingLog.LOG_INFO,
                            "Unmatched feature : %d -> %d" % (first_back_node, node))
                
                back_node = first_back_node
                while node != back_node:
                    next_back_node = stack.pop()
                    for feature_id in feature_index[(next_back_node, back_node)]:
                        layer.select(feature_id)
                    back_node = next_back_node

            # progress.setPercentage(int(current * total))

        for node in node_index.keys():
            if not seen_nodes.has_key(node):
                connect(node)
