# -*- coding: utf-8 -*-

"""
Graph Iterator

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from math import sqrt
from collections import defaultdict

from heapq import heappush, heappop
from functools import total_ordering
import numpy as np

from qgis.core import NULL

@total_ordering
class QueueEntry(object):

    def __init__(self, key, parent, weight, max_cost):

        self.key = key
        self.parent = parent
        self.weight = weight
        self.max_cost = max_cost
        self.duplicate = False
        self.settled = False

    def __hash__(self):
        return self.key.__hash__()

    def __lt__(self, other):
        return self.weight < other.weight

    def __eq__(self, other):
        if other is None:
            return False
        return self.weight == other.weight

# def other(x, a, b):

#     if x == a:
#         return b
#     else:
#         return a

class EdgeData(object):

    def __init__(self, edge_id, from_node, to_node, weight, unit_cost):

        self.edge_id = edge_id
        self.from_node = from_node
        self.to_node = to_node
        self.weight = weight
        self.unit_cost = unit_cost

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

        length = edge.geometry().length()
        # return self.unit_cost(edge) * length
        return length

    def unit_cost(self, edge):

        if self.weight_field is None:
            return 1.0

        weight = edge.attribute(self.weight_field)

        if weight == NULL:
            weight = self.max_weight

        return weight

    def edges(self, node_key):

        if node_key in self.index:
            for edge_data in self.index[node_key]:
                w = edge_data.unit_cost
                if w < self.max_weight:
                    yield edge_data

class UndirectedEdgeLayerGraph(EdgeLayerGraph):

    def build_index(self):

        index = defaultdict(list)

        for edge in self.edge_layer.getFeatures():

            a = edge.attribute(self.node_a_field)
            b = edge.attribute(self.node_b_field)

            edge_data = EdgeData(edge.id(), a, b, self.weight(edge), self.unit_cost(edge))
            index[a].append(edge_data)

            edge_data = EdgeData(edge.id(), b, a, self.weight(edge), self.unit_cost(edge))
            index[b].append(edge_data)

        return index

class DirectedEdgeLayerGraph(EdgeLayerGraph):

    def build_index(self):

        index = defaultdict(list)

        for edge in self.edge_layer.getFeatures():

            a = edge.attribute(self.node_a_field)
            b = edge.attribute(self.node_b_field)

            edge_data = EdgeData(edge.id(), a, b, self.weight(edge), self.unit_cost(edge))
            index[a].append(edge_data)

        return index

class GraphIterator(object):

    def __init__(self, graph, origin):

        self.graph = graph
        self.origin = origin 

    def __enter__(self):

        self.heap = list()
        self.seen = dict()
        entry = QueueEntry(self.origin, None, 0, 0)
        heappush(self.heap, entry)
        self.seen[self.origin] = entry

        return self

    def __exit__(self,  exc_type, exc_val, exc_tb):

        self.heap = None
        self.seen = None

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

        for edge_data in self.graph.edges(next_entry.key):

            node = edge_data.to_node
            edge_weight = edge_data.weight
            edge_cost = edge_data.unit_cost

            weight = next_entry.weight + edge_weight
            # length = next_entry.length + edge.length
            max_cost = max(next_entry.max_cost, edge_cost)
            # weight = length * max_weight

            if node in self.seen:
                seen_entry = self.seen[node]
                if weight < seen_entry.weight:
                    seen_entry.duplicate = True
                    new_entry = QueueEntry(node, next_entry, weight, max_cost)
                    heappush(self.heap, new_entry)
                    self.seen[node] = new_entry
            else:
                new_entry = QueueEntry(node, next_entry, weight, max_cost)
                heappush(self.heap, new_entry)
                self.seen[node] = new_entry

        next_entry.settled = True
        return next_entry

    def is_settled(self, key):

        if key in self.seen:
            return self.seen[key].settled

        return False

    def shortestPathLength(self, key):

        if key in self.seen:
            return self.seen[key].weight

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
