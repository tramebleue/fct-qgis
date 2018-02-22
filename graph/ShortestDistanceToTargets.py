# -*- coding: utf-8 -*-

"""
***************************************************************************
    ShortestDistanceToTargets.py
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
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt

from heapq import heappush, heappop
from functools import total_ordering
import numpy as np

@total_ordering
class QueueEntry(object):

    def __init__(self, key, parent, weight):
        self.key = key
        self.parent = parent
        self.weight = weight
        self.duplicate = False
        self.settled = False

    def __hash__(self):
        return self.key.__hash__()

    def __lt__(self, other):
        return self.weight < other.weight

    def __eq__(self, other):
        return self.weight == other.weight

def other(x, a, b):

    if x == a:
        return b
    else:
        return a

class EdgeData(object):

    def __init__(self, edge_id, from_node, to_node, weight):
        
        self.edge_id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.weight = weight

class EdgeLayerGraph(object):

    def __init__(self, edge_layer, node_a_field, node_b_field, weight_field, max_weight):
        
        self.edge_layer = edge_layer
        self.node_a_field = node_a_field
        self.node_b_field = node_b_field
        self.weight_field = weight_field
        self.max_weight = max_weight
        self.index = self.build_index()

    def build_index(self):

        raise NotImplementedError('Abstract class %s' % self.__class__)


    def other_node(self, edge, node):

        if edge.attribute(self.node_a_field) == node:
            return edge.attribute(self.node_b_field)
        else:
            return edge.attribute(self.node_a_field)

    def weight(self, edge):

        return edge.attribute(self.weight_field)

    def edges(self, node_key):

        if self.index.has_key(node_key):
            for edge_data in self.index[node_key]:
                w = edge_data.weight
                if w > 0 and w < self.max_weight:
                    yield edge_data.to_node, w

class UndirectedEdgeLayerGraph(EdgeLayerGraph):

    def build_index(self):

        index = dict()
        
        for edge in self.edge_layer.getFeatures():
            a = edge.attribute(self.node_a_field)
            b = edge.attribute(self.node_b_field)
            for node in (a, b):
                edge_data = EdgeData(edge.id(), node, other(node, a, b), self.weight(edge))
                if not index.has_key(node):
                    index[node] = [ edge_data ]
                else:
                    index[node].append(edge_data)

        return index

class DirectedEdgeLayerGraph(EdgeLayerGraph):

    def build_index(self):

        index = dict()
        
        for edge in self.edge_layer.getFeatures():
            a = edge.attribute(self.node_a_field)
            b = edge.attribute(self.node_b_field)
            edge_data = EdgeData(edge.id(), a, b, self.weight(edge))
            if not index.has_key(a):
                index[a] = [ edge_data ]
            else:
                index[a].append(edge_data)

        return index

class GraphIterator(object):

    def __init__(self, graph, origin):

        self.graph = graph
        self.heap = list()
        self.seen = dict()
        entry = QueueEntry(origin, None, 0)
        heappush(self.heap, entry)
        self.seen[origin] = entry

    def __iter__(self):
        try:
            while True:
                yield self.__next__()
        except StopIteration:
            pass

    def __next__(self):

        if len(self.heap) == 0:
            raise StopIteration

        next_entry = heappop(self.heap)
        
        while (next_entry.duplicate and len(self.heap) > 0):
            next_entry = heappop(self.heap)
        
        if next_entry is None or next_entry.duplicate:
            raise StopIteration
        
        for node, edge_weight in self.graph.edges(next_entry.key):
            
            weight = next_entry.weight + edge_weight
            if self.seen.has_key(node):
                seen_entry = self.seen[node]
                if weight < seen_entry.weight:
                    seen_entry.duplicate = True
                    new_entry = QueueEntry(node, next_entry, weight)
                    heappush(self.heap, new_entry)
                    self.seen[node] = new_entry
            else:
                new_entry = QueueEntry(node, next_entry, weight)
                heappush(self.heap, new_entry)
                self.seen[node] = new_entry

        next_entry.settled = True
        return next_entry

    def is_settled(self, key):
        if self.seen.has_key(key):
            return self.seen[key].settled
        else:
            return False

    def shortestPathLength(self, key):
        if self.seen.has_key(key):
            return self.seen[key].weight
        else:
            return np.infty

    def path(self, key):
        path = list()
        entry = self.seen.get(key)
        weight = entry.weight
        while entry != None:
            path.append(entry.key)
            entry = entry.parent

        path.reverse()
        return path, weight

    def release(self):
        self.graph = None
        self.heap = None
        self.seen = None

class ShortestDistanceToTargets(GeoAlgorithm):

    NODE_LAYER = 'NODE_LAYER'
    FID_FIELD = 'FID_FIELD'
    DISTANCE_FIELD = 'DISTANCE'
    NHOPS_FIELD = 'NHOPS'
    MAX_WEIGHT_FIELD = 'MAXW'

    TARGET_LAYER = 'TARGET_LAYER'
    TARGET_FID_FIELD = 'TARGET_FID_FIELD'

    EDGE_LAYER = 'EDGE_LAYER'
    GRAPH_TYPE = 'GRAPH_TYPE'
    NODE_A_FIELD = 'NODE_A_FIELD'
    NODE_B_FIELD = 'NODE_B_FIELD'
    WEIGHT_FIELD = 'WEIGHT_FIELD'
    MAX_WEIGHT = 'MAX_WEIGHT'

    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Shortest Distance To Targets')
        self.group, self.i18n_group = self.trAlgorithm('Graph Routines')

        self.addParameter(ParameterVector(self.NODE_LAYER,
                                          self.tr('Source Nodes Layer'), [ParameterVector.VECTOR_TYPE_POINT]))
        
        self.addParameter(ParameterTableField(self.FID_FIELD,
                                          self.tr('Source Nodes Id Field'),
                                          parent=self.NODE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.TARGET_LAYER,
                                          self.tr('Target Nodes Layer'), [ParameterVector.VECTOR_TYPE_POINT]))
        
        self.addParameter(ParameterTableField(self.TARGET_FID_FIELD,
                                          self.tr('Target Nodes Id Field'),
                                          parent=self.TARGET_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.EDGE_LAYER,
                                          self.tr('Edge Layer'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterSelection(self.GRAPH_TYPE,
                                             self.tr('Graph Type'),
                                             options=[self.tr('Undirected'), self.tr('Directed')], default=0))
        
        self.addParameter(ParameterTableField(self.NODE_A_FIELD,
                                          self.tr('Node A Field'),
                                          parent=self.EDGE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.NODE_B_FIELD,
                                          self.tr('Node B Field'),
                                          parent=self.EDGE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.WEIGHT_FIELD,
                                          self.tr('Distance Field'),
                                          parent=self.EDGE_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterNumber(self.MAX_WEIGHT, self.tr('Max Weight'),
                                          default=0.0, minValue=0.0, optional=True))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Shortest Distance')))


    def processAlgorithm(self, progress):

        node_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.NODE_LAYER))
        fid_field = self.getParameterValue(self.FID_FIELD)

        target_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.TARGET_LAYER))
        target_fid_field = self.getParameterValue(self.TARGET_FID_FIELD)

        edge_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.EDGE_LAYER))
        node_a_field = self.getParameterValue(self.NODE_A_FIELD)
        node_b_field = self.getParameterValue(self.NODE_B_FIELD)
        weight_field = self.getParameterValue(self.WEIGHT_FIELD)
        max_weight = self.getParameterValue(self.MAX_WEIGHT)

        progress.setText(self.tr("Build index and graph ..."))
        

        targets = set()
        for target in vector.features(target_layer):
            targets.add(target.attribute(target_fid_field))

        if self.getParameterValue(self.GRAPH_TYPE) == 0:
            graph = UndirectedEdgeLayerGraph(edge_layer, node_a_field, node_b_field, weight_field, max_weight)
        else:
            graph = DirectedEdgeLayerGraph(edge_layer, node_a_field, node_b_field, weight_field, max_weight)

        progress.setText(self.tr("Compute shortest path to targets for each input node ..."))
        
        fields = [
            QgsField(fid_field, QVariant.Int, len=10),
            QgsField(self.DISTANCE_FIELD, QVariant.Double, len=8, prec=2),
            QgsField(self.MAX_WEIGHT_FIELD, QVariant.Double, len=8, prec=2),
            QgsField(self.NHOPS_FIELD, QVariant.Int, len=5)
        ]
        writer = writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields,
            node_layer.dataProvider().geometryType(),
            node_layer.crs())
        total = 100.0 / node_layer.featureCount()

        for current, feature in enumerate(vector.features(node_layer)):

            origin = feature.attribute(fid_field)
            iterator = GraphIterator(graph, origin)
            
            for entry in iterator:
                if entry.key in targets:
                    weight = entry.weight
                    break
            else:
                weight = np.infty

            if weight != np.infty:
                
                path, weight = iterator.path(entry.key)
                weights = [ iterator.seen[k].weight for k in path ]
                max_w = max([ weights[0] ] + [ weights[i+1] - w for i, w in enumerate(weights[:-1])  ])
                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes([
                        feature.attribute(fid_field),
                        float(weight),
                        float(max_w),
                        len(path)
                    ])
                writer.addFeature(outfeature)

            else:

                ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "No path found from node %s" % origin)

            iterator.release()

            progress.setPercentage(int(current * total))