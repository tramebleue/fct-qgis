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
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt


class SelectDownstreamComponents(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    # OUTPUT_LAYER = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Select Downstream Components')
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

        # self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Stream')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        to_node_field = self.getParameterValue(self.TO_NODE_FIELD)

        progress.setText(self.tr("Build layer index ..."))

        # Index : Node A -> Edges starting from Node A
        from_node_index = dict()
        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(layer.getFeatures()):

            from_node = feature.attribute(from_node_field)
            if from_node_index.has_key(from_node):
                from_node_index[from_node].append(feature.id())
            else:
                from_node_index[from_node] = [ feature.id() ]
            
            progress.setPercentage(int(current * total))


        progress.setText(self.tr("Select connected reaches ..."))

        process_stack = [ segment for segment in layer.selectedFeatures() ]
        selection = set()

        while process_stack:

            segment = process_stack.pop()
            selection.add(segment.id())
            to_node = segment.attribute(to_node_field)

            if from_node_index.has_key(to_node):
                q = QgsFeatureRequest().setFilterFids(from_node_index[to_node])
                for next_segment in layer.getFeatures(q):
                    # Prevent infinite loop
                    if not next_segment.id() in selection:
                        process_stack.append(next_segment)

        layer.setSelectedFeatures(list(selection))