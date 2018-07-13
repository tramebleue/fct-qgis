
# -*- coding: utf-8 -*-

"""
***************************************************************************
    SelectStreamFromSourceToOutlet.py
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
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper

from collections import defaultdict
from functools import total_ordering
from heapq import heappush, heappop
from math import sqrt

@total_ordering
class Pair(object):

    @classmethod
    def root(cls):

        return Pair(None, None, None, 0.0, float('inf'))

    def __init__(self, n1, n2, parent, distance, meas2):

        self.n1 = n1
        self.n2 = n2
        self.meas2 = meas2
        self.parent = parent
        # self.children = list()
        self.duplicate = False

        if parent is not None:

            self.distance = parent.distance + distance
            self.length = parent.length + 1
        
        else:
        
            self.distance = distance
            self.length = 0

    def __hash__(self): 
        return hash((self.n1, self.n2))

    def __lt__(self, other):
        return self.distance < other.distance

    def __eq__(self, other):
        return self.distance == other.distance

    def __repr__(self):

        return 'Pair (%s, %s)' % (self.n1, self.n2)

class MatchNetworkNodesTopology(GeoAlgorithm):

    NETWORK1 = 'NETWORK1'
    NODES1 = 'NODES1'
    NETWORK2 = 'NETWORK2'
    NODES2 = 'NODES2'
    MAX_DISTANCE = 'MAX_DISTANCE'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Match Network Nodes Topology')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.NETWORK1,
                                          self.tr('Source Network'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterVector(self.NODES1,
                                          self.tr('Source Nodes'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterVector(self.NETWORK2,
                                          self.tr('Target Network'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterVector(self.NODES2,
                                          self.tr('Target Nodes'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterNumber(self.MAX_DISTANCE,
                                          self.tr('Maximum Search Distance'),
                                          minValue=0.0, default=500.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Paired Nodes')))

    def processAlgorithm(self, progress):

        network1 = dataobjects.getObjectFromUri(self.getParameterValue(self.NETWORK1))
        network2 = dataobjects.getObjectFromUri(self.getParameterValue(self.NETWORK2))
        nodes1 = dataobjects.getObjectFromUri(self.getParameterValue(self.NODES1))
        nodes2 = dataobjects.getObjectFromUri(self.getParameterValue(self.NODES2))
        max_distance = self.getParameterValue(self.MAX_DISTANCE)

        node_a_field = 'NODE_A'
        node_b_field = 'NODE_B'
        gid_field = 'GID'
        meas_field = 'MEAS'

        # Adjacency index : node -> downstream nodes
        # index1 = node a1 : list(node b1)
        # index2 = node a2 : list(node b2)

        def adjacency(network):

            index = defaultdict(list)
            total = 100.0 / network.featureCount()

            for current, feature in enumerate(network.getFeatures()):

                a = feature.attribute(node_a_field)
                b = feature.attribute(node_b_field)
                index[a].append(b)

                progress.setPercentage(int(current * total))

            return index

        # def confluences(network):

        #     index = defaultdict(list)
        #     total = 100.0 / network.featureCount()

        #     for current, feature in enumerate(network.getFeatures()):

        #         a = feature.attribute(node_a_field)
        #         b = feature.attribute(node_b_field)
        #         index[b].append(a)

        #         progress.setPercentage(int(current * total))

        #     return [ b for b, edges in index.items() if len(edges) > 1 ]

        index1 = adjacency(network1)
        index2 = adjacency(network2)
        # confluences1 = confluences1(nodes1)
        network2_index = QgsSpatialIndex(network2.getFeatures())

        # points1 = node n1 : (point, meas, fid)
        # points2 = node n2 : (point, meas, fid)

        def node_index(layer):

            index = dict()
            total = 100.0 / layer.featureCount()

            for current, feature in enumerate(layer.getFeatures()):

                gid = feature.attribute(gid_field)
                meas = feature.attribute(meas_field)

                index[gid] = (feature.geometry().asPoint(), meas, feature.id())

                progress.setPercentage(int(current * total))

            return index

        points1 = node_index(nodes1)
        points2 = node_index(nodes2)

        sources = set(index1.keys()) - set([ b for bnodes in index1.values() for b in bnodes ])
        # sort sources by descending distance to outlet

        def sort_by_desc_meas(a, b):

            pa, ma, fa = points1.get(a)
            pb, mb, fb = points1.get(b)

            if ma == mb:
                return 0
            elif ma > mb:
                return -1
            else:
                return 1

        sources = list(sources)
        sources.sort(sort_by_desc_meas)

        def distance(n1, n2):

            p1, m1, fid1 = points1.get(n1)
            p2, m2, fid2 = points2.get(n2)
            return sqrt(p1.sqrDist(p2))

        def downstream_nodes(node, index, points):

            # for n in index.get(node):
            #     yield n

            if index.has_key(node):

                stack = list(index.get(node))
                seen_nodes = set()

                while stack:

                    n = stack.pop()

                    if n in seen_nodes:
                        continue

                    seen_nodes.add(n)

                    if points.has_key(n):

                        yield n

                    else:

                        if index.has_key(n):
                            stack.extend(index.get(n))

        def downstream_sequence_of_nodes(node, n1, index, points, max_distance):

            if index.has_key(node):
            
                stack = list(index.get(node))
                # p0, m0, fid0 = points.get(node)
                seen_nodes = set()

                while stack:

                    n = stack.pop()

                    if n in seen_nodes:
                        continue

                    seen_nodes.add(n)

                    if not points.has_key(n):
                        
                        if index.has_key(n):
                            stack.extend(index.get(n))

                        continue

                    p, m, fid = points.get(n)

                    if index.has_key(n):
                        
                        stack.extend(index.get(n))

                    if distance(n1, n) < max_distance:
                    # if True:

                        yield n, m

        def match_source(point, network, network_index, index, points, max_distance):

            pgeom = QgsGeometry.fromPoint(point)
            box = pgeom.boundingBox()
            box.grow(max_distance)
            
            for fid in network_index.intersects(box):

                segment = network.getFeatures(QgsFeatureRequest(fid)).next()
                distance = segment.geometry().distance(pgeom)

                if distance < max_distance:

                    node = segment.attribute(node_a_field)

                    if not points.has_key(node):

                        for n in downstream_nodes(node, index, points):
                            yield n
                            break

                    else:

                        yield node

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                nodes1,
                QgsField('PAIRID', QVariant.Int, len=10),
                QgsField('PAIRX', QVariant.Double, len=10, prec=2),
                QgsField('PAIRY', QVariant.Double, len=10, prec=2)
            ),
            nodes1.dataProvider().geometryType(),
            nodes1.crs())

        def output(pair):
            
            p1, m1, fid1 = points1.get(pair.n1)

            feature = nodes1.getFeatures(QgsFeatureRequest(fid1)).next()
            
            out_feature = QgsFeature()
            out_feature.setGeometry(feature.geometry())

            if points2.has_key(pair.n2):

                p2, m2, fid2 = points2.get(pair.n2)
                out_feature.setAttributes(
                    feature.attributes() + [
                        pair.n2,
                        p2.x(),
                        p2.y()
                    ])

            else:

                out_feature.setAttributes(
                    feature.attributes() + [
                        None,
                        None,
                        None
                    ])

            writer.addFeature(out_feature)

        # pairs = n1 : pair
        pairs = dict()
        paired_nodes = set()

        while sources:

            source = sources.pop(0)

            if not points1.has_key(source):

                sources.extend(downstream_nodes(source, index1, points1))
                continue

            seen_pairs = dict()
            tree_size = 0

            point, meas, fid = points1.get(source)
            root = Pair.root()
            stack = list()
            parent = root
            source_matched = False
            
            for s2 in match_source(point, network2, network2_index, index2, points2, max_distance):

                p2, m2, fid2 = points2[s2]
                child = Pair(source, s2, root, distance(source, s2), m2)
                # root.children.append(child)
                tree_size += 1
                heappush(stack, child)
                seen_pairs[(source, s2)] = child
                source_matched = True

            if not source_matched:

                sources.extend(downstream_nodes(source, index1, points1))

            # Find all possible pairs descending from source

            while stack:

                parent = heappop(stack)
                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'At %s' % parent)

                if parent.duplicate:
                    continue

                a1 = parent.n1
                a2 = parent.n2

                if a1 in paired_nodes:
                    break

                if a2 is None:

                    current = parent

                    while current is not root and a2 is None:
                    
                        a2 = current.n2
                        current = current.parent

                if index1.has_key(a1):

                    # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Downstream nodes %s' % list(downstream_nodes(a1, index1, points1)))

                    for b1 in downstream_nodes(a1, index1, points1):

                        matched = False

                        # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Downstream sequence of A2 %s : %s' % (a2, list(downstream_sequence_of_nodes(a2, b1, index2, points2, max_distance))))

                        for b2, m2  in downstream_sequence_of_nodes(a2, b1, index2, points2, max_distance):

                            if seen_pairs.has_key((b1, b2)):

                                seen_pair = seen_pairs.get((b1, b2))
                                if seen_pair.distance > parent.distance + distance(b1, b2):

                                    seen_pair.duplicate = True
                                    child = Pair(b1, b2, parent, distance(b1, b2), m2)
                                    # parent.children.append(child)
                                    tree_size += 1
                                    heappush(stack, child)
                                    seen_pairs[(b1, b2)] = child

                            else:
                                
                                child = Pair(b1, b2, parent, distance(b1, b2), m2)
                                # parent.children.append(child)
                                tree_size += 1
                                heappush(stack, child)
                                seen_pairs[(b1, b2)] = child
                            
                            
                            matched = True

                            # if tree_size > 100000:
                            #     ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'To %s' % child)
                            #     raise GeoAlgorithmExecutionException('Exit Infinite Loop from source %s' % source)

                        if not matched:

                            child = Pair(b1, None, parent, max_distance, float('inf'))
                            # parent.children.append(child)
                            tree_size += 1
                            heappush(stack, child)
                            seen_pairs[(b1, None)] = child

                else:

                    # we are done : we reached network outlet
                    break

            # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Tree size from source %s : %d' % (source, tree_size))

            # Backtrack sequence of pairs

            # pair = best_match
            pair = parent

            while pair is not root:

                if pairs.has_key(pair.n1):

                    existing = pairs[pair.n1]
                    # TODO find first common downstream node
                    if pair.meas2 < existing.meas2:
                        pairs[pair.n1] = pair

                else:

                    pairs[pair.n1] = pair

                paired_nodes.add(pair.n1)
                pair = pair.parent

        # Output pairs

        for pair in pairs.values():

                output(pair)

        # Output unmatch ?

        for feature in nodes1.getFeatures():

            gid = feature.attribute(gid_field)

            if not gid in pairs.keys():

                out_feature = QgsFeature()
                out_feature.setGeometry(feature.geometry())
                out_feature.setAttributes(
                    feature.attributes() + [
                        None,
                        None,
                        None
                    ])

                writer.addFeature(out_feature)





