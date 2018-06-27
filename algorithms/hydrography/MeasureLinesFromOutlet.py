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

from ...core import vector as vector_helper
from functools import partial
from collections import defaultdict
from math import sqrt

def index_by(i, d, x):
    d[x[i]].append(x)
    return d

class MeasureLinesFromOutlet(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Measure Lines From Outlet')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

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

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Measured Lines')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)

        # Step 1 - Find sources and build adjacency index

        progress.setText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount()
        adjacency = list()

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            adjacency.append((a, b, edge.id(), edge.geometry().length()))
            
            progress.setPercentage(int(current * total))

        anodes = set([ a for a,b,e,l in adjacency ])
        bnodes = set([ b for a,b,e,l in adjacency ])

        outlets = bnodes - anodes
        edge_index = reduce(partial(index_by, 1), adjacency, defaultdict(list))

        measures = { node: 0.0 for node in outlets }
        stack = list(outlets)

        progress.setText(self.tr("Find maximum distance from outlet ..."))
        total = 100.0 / layer.featureCount()
        current = 0
        seen_nodes = set(outlets)

        while stack:

            # bredth first
            node = stack.pop(0)
            m = measures[node]

            for a, b, e, l in edge_index[node]:
                # node === b
                ma = measures.get(a, 0.0)
                if ma < m + l:
                    measures[a] = m + l

                if not a in seen_nodes:
                    seen_nodes.add(a)
                    stack.append(a)

            current = current + 1
            progress.setPercentage(int(current * total))

        progress.setText(self.tr("Output measured lines ..."))
        total = 100.0 / layer.featureCount()

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                layer,
                QgsField('MEASA', QVariant.Double, len=10, prec=2),
                QgsField('MEASB', QVariant.Double, len=10, prec=2),
                QgsField('LENGTH', QVariant.Double, len=6, prec=2)
            ),
            layer.dataProvider().geometryType(),
            layer.crs())

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            m = measures.get(b, 0.0)
            length = edge.geometry().length()

            out_feature = QgsFeature()
            out_feature.setGeometry(edge.geometry())
            out_feature.setAttributes(edge.attributes() + [
                    m + length,
                    m,
                    length
                ])
            writer.addFeature(out_feature)

            progress.setPercentage(int(current * total))

