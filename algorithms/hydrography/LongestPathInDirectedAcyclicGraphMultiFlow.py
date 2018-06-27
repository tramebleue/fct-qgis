# -*- coding: utf-8 -*-

"""
***************************************************************************
    LongestPathInDirectedAcyclicGraph.py
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
from collections import defaultdict
from functools import partial
from math import sqrt

def index_by(i, d, x):
    d[x[i]].append(x)
    return d

class PathInfo(object):

    def __init__(self, start_node):

        self.start_node = start_node
        self.end_node = None
        self.length = 0
        self.edges = list()
        self.diverging = False

    def add(self, node, edge, new_length):

        self.end_node = node
        self.edges.append(edge)
        self.length = new_length
        return self

class NodeInfo(object):

    def __init__(self, node, length=0.0, path=None):

        self.node = node
        self.length = length
        self.out_degree = 0
        if path is None:
            path = PathInfo(self)
        self.path = path
        self.index = -1

    def add(self, node, edge, new_length):
        
        path = self.path
        self.index = len(path.edges) - 1

        successor = NodeInfo(node, new_length, path)
        self.out_degree = self.out_degree + 1
        path.add(successor, edge, new_length)

        return successor

    def divergesTo(self, b):

        return (self.path.start_node.node == b.path.start_node.node)


class LongestPathInDirectedAcyclicGraphMultiFlow(GeoAlgorithm):

    EDGE_LAYER = 'EDGE_LAYER'
    NODE_A_FIELD = 'NODE_A_FIELD'
    NODE_B_FIELD = 'NODE_B_FIELD'

    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Longest Path In DAG (Multiple Flow)')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

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

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Longest Path')))

    
    def processAlgorithm(self, progress):

        edge_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.EDGE_LAYER))
        node_a_field = self.getParameterValue(self.NODE_A_FIELD)
        node_b_field = self.getParameterValue(self.NODE_B_FIELD)
        
        # Step 1

        progress.setText(self.tr("Build adjacency index ..."))

        total = 100.0 / edge_layer.featureCount()
        adjacency = list()

        for current, edge in enumerate(edge_layer.getFeatures()):

            a = edge.attribute(node_a_field)
            b = edge.attribute(node_b_field)
            adjacency.append((a, b, edge.id(), edge.geometry().length()))
            progress.setPercentage(int(current * total))

        anodes = set([ a for a,b,e,l in adjacency ])
        bnodes = set([ b for a,b,e,l in adjacency ])
        # nodes = anodes.union(bnodes)
        sources = anodes - bnodes
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 2

        progress.setText(self.tr("Search for longest path ..."))

        seen_nodes = dict()
        max_length = 0
        max_path = None
        stack = list(sources)

        for source in sources:
            seen_nodes[source] = NodeInfo(source)

        diverging = False

        while stack:

            node = stack.pop()

            if not aindex.has_key(node):
                continue

            for a, b, edge, length in aindex[node]:

                current_length = seen_nodes[a].length + length

                if seen_nodes.has_key(b):
                    
                    if seen_nodes[a].divergesTo(seen_nodes[b]):

                        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Closing diverticule")
                        junction = seen_nodes[a].add(b, edge, current_length)
                        if seen_nodes[b].length < current_length:
                            seen_nodes[b] = junction
                            continue
                    
                    if seen_nodes[b].length >= current_length:
                        continue

                seen_nodes[b] = seen_nodes[a].add(b, edge, current_length)
                stack.append(b)

                if current_length > max_length:
                    max_length = current_length
                    max_path = seen_nodes[b].path

        # Step 3

        progress.setText(self.tr("Output longest path ..."))

        assert(max_path is not None)

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Longest path is %.2f long with %d edges" % (max_length, len(max_path.edges)))

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            edge_layer.fields().toList(),
            edge_layer.dataProvider().geometryType(),
            edge_layer.crs())
        
        total = 100.0 / len(max_path.edges)

        for current, edge_id in enumerate(max_path.edges):

            edge = edge_layer.getFeatures(QgsFeatureRequest(edge_id)).next()
            writer.addFeature(edge)    

            progress.setPercentage(int(current * total))