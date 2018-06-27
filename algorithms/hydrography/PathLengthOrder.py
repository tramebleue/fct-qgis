# -*- coding: utf-8 -*-

"""
***************************************************************************
    PathLengthOrder.py
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

from heapq import heappush, heappop
from functools import total_ordering
from functools import partial
from collections import defaultdict
from math import sqrt

def index_by(i, d, x):
    d[x[i]].append(x)
    return d

@total_ordering
class SourceEntry(object):

    def __init__(self, key, distance):
        self.key = key
        # Use negative distance to sort sources
        # max distance to min distance (max heap)
        self.distance = -distance

    def __hash__(self):
        return self.key.__hash__()

    def __lt__(self, other):
        return self.distance < other.distance

    def __eq__(self, other):
        return self.distance == other.distance


class PathLengthOrder(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    DISTANCE_FIELD = 'DISTANCE_FIELD'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Path Length Order')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterTableField(self.DISTANCE_FIELD,
                                          self.tr('Distance Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        self.addParameter(ParameterTableField(self.FROM_NODE_FIELD,
                                          self.tr('From Node Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        self.addParameter(ParameterTableField(self.TO_NODE_FIELD,
                                          self.tr('To Node Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Path Length Order')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)
        distance_field = self.getParameterValue(self.DISTANCE_FIELD)

        # Step 1 - Find sources and build djacency index

        progress.setText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount()
        adjacency = list()

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append((a, b, edge.id(), edge.attribute(distance_field)))
            
            progress.setPercentage(int(current * total))

        anodes = set([ a for a,b,e,d in adjacency ])
        bnodes = set([ b for a,b,e,d in adjacency ])
        # No edge points to a source,
        # then sources are not in bnodes
        sources = anodes - bnodes

        # Index : Node A -> Edges starting from A
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 2 - Sort sources by descending distance
        
        queue = list()
        for source in sources:
            for a, b, edge_id, distance in aindex[source]:
                heappush(queue, SourceEntry(edge_id, distance))

        # Step 3 - Output edges starting from maximum distance source to outlet ;
        #          when outlet is reached,
        #          continue from next maximum distance source
        #          until no edge remains

        progress.setText(self.tr("Sort subgraphs by descending source distance"))
        
        seen_edges = dict()
        current = 0
        total = 100.0 / len(sources)
        progress.setPercentage(0)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.fields().toList() + [
                QgsField('PATHID', QVariant.Int, len=5),
                QgsField('PRANK', QVariant.Int, len=5),
                QgsField('PLENGTH', QVariant.Double, len=10, prec=2)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        while queue:

            entry = heappop(queue)
            edge = layer.getFeatures(QgsFeatureRequest(entry.key)).next()
            process_stack = [ edge ]
            selection = set()
            rank = 1
            length = 0

            while process_stack:

                edge = process_stack.pop()
                selection.add(edge.id())
                length += edge.geometry().length()
                to_node = edge.attribute(to_node_field)

                if aindex.has_key(to_node):
                    
                    edges = [ e for a,b,e,d in aindex[to_node] ]
                    q = QgsFeatureRequest().setFilterFids(edges)
                    
                    for next_edge in layer.getFeatures(q):
                    
                        next_id = next_edge.id()
                        if seen_edges.has_key(next_id):
                            rank = seen_edges[next_id] + 1
                        elif not next_id in selection:
                            process_stack.append(next_edge)

            q = QgsFeatureRequest().setFilterFids(list(selection))
            for feature in layer.getFeatures(q):

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [
                        current,
                        rank,
                        length
                    ])
                writer.addFeature(outfeature)
                seen_edges[feature.id()] = rank


            current = current + 1
            progress.setPercentage(int(current * total))