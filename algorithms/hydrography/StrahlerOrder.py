# -*- coding: utf-8 -*-

"""
***************************************************************************
    StrahlerOrder.py
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

def count_by(i, d, x):
    d[x[i]] = d[x[i]] + 1
    return d

class StrahlerOrder(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Strahler Order')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.FROM_NODE_FIELD,
                                          self.tr('From Node Field'),
                                          parent=self.INPUT_LAYER,
                                          # default='NODE_A',
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.TO_NODE_FIELD,
                                          self.tr('To Node Field'),
                                          # default='NODE_B',
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Strahler Order')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)

        # Step 1 - Build adjacency index

        progress.setText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount()
        adjacency = list()

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append((a, b, edge.id()))
            
            progress.setPercentage(int(current * total))

        # Step 2 - Find sources and compute confluences in-degree

        anodes = set([ a for a,b,e in adjacency ])
        bnodes = set([ b for a,b,e in adjacency ])
        # No edge points to a source,
        # then sources are not in bnodes
        sources = anodes - bnodes

        # Confluences in-degree
        bcount = reduce(partial(count_by, 1) , adjacency, defaultdict(lambda: 0))
        confluences = { node: indegree for node, indegree in bcount.items() if indegree > 1 }

        # Index : Node A -> Edges starting from A
        aindex = reduce(partial(index_by, 0), adjacency, defaultdict(list))

        # Step 3 - Prune sources/leaves iteratively

        progress.setText(self.tr("Enumerate segments by Strahler order ..."))

        current = 0
        total = 100.0 / layer.featureCount()
        progress.setPercentage(0)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.fields().toList() + [
                QgsField('STRAHLER', QVariant.Int, len=5),
            ],
            layer.dataProvider().geometryType(),
            layer.crs())

        queue = list(sources)
        order = 1

        while True:

            while queue:

                a = queue.pop()

                for a, b, edgeid in aindex[a]:

                    edge = layer.getFeatures(QgsFeatureRequest(edgeid)).next()
                    feature = QgsFeature()
                    feature.setGeometry(edge.geometry())
                    feature.setAttributes(edge.attributes() + [
                            order
                        ])
                    writer.addFeature(feature)

                    current = current + 1
                    progress.setPercentage(int(current * total))

                    if confluences.has_key(b):
                        confluences[b] = confluences[b] - 1
                    else:
                        queue.append(b)

            queue = [ node for node, indegree in confluences.items() if indegree == 0 ]
            confluences = { node: indegree for node, indegree in confluences.items() if indegree > 1 }
            order = order + 1

            # if not confluences and not queue:
            if not queue:
                break