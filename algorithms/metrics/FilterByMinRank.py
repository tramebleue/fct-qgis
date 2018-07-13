# -*- coding: utf-8 -*-

"""
***************************************************************************
    WeightedMean.py
    ---------------------
    Date                 : February 2018
    Copyright            : (C) 2018 by Christophe Rousson
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

from qgis.core import QgsFeature, QgsField, QgsPoint, QgsGeometry, QgsFeatureRequest
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper
from collections import defaultdict

class FilterByMinRank(GeoAlgorithm):

    INPUT = 'INPUT'
    GROUP_FIELD = 'GROUP_FIELD'
    RANK_FIELD = 'RANK_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Filter By Minimum Rank')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Metrics (Polyline)'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.GROUP_FIELD,
                                          self.tr('Group Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addParameter(ParameterTableField(self.RANK_FIELD,
                                          self.tr('Rank Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Filtered')))

    def processAlgorithm(self, progress):

    	layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
    	group_field = self.getParameterValue(self.GROUP_FIELD)
        rank_field = self.getParameterValue(self.RANK_FIELD)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList(),
            layer.dataProvider().geometryType(),
            layer.crs())

        progress.setText(self.tr('Build input index ...'))

        features = vector.features(layer)
        total = 100.0 / len(features)

        groups = defaultdict(list)

        for current, feature in enumerate(features):

        	group = feature.attribute(group_field)
        	rank = feature.attribute(rank_field)

        	groups[group].append((feature.id(), rank))

        	progress.setPercentage(int(current * total))

        progress.setText(self.tr('Filter features by priority ...'))

        total = 100.0 / len(groups)

        for current, group in enumerate(groups.keys()):

            min_rank = min([ rank for fid, rank in groups[group] ])
            
            for fid, rank in groups[group]:

                if rank == min_rank:
                    
                    feature = layer.getFeatures(QgsFeatureRequest(fid)).next()
                    writer.addFeature(feature)

        	progress.setPercentage(int(current * total))