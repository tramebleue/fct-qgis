# -*- coding: utf-8 -*-

"""
***************************************************************************
    Sequencing2.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFeatureRequest, QgsFields, QgsField
from qgis.core import QgsVectorLayer
from qgis.core import NULL
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from ...core import vector as vector_helper

from collections import defaultdict

class MarkMainDrain(GeoAlgorithm):

    NETWORK = 'NETWORK'
    COST_FIELD = 'COST_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Mark Main Drain')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        self.addParameter(ParameterVector(self.NETWORK,
                                          self.tr('Input Network Layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        self.addParameter(ParameterTableField(self.COST_FIELD,
                                          self.tr('Traversal Cost Field'),
                                          parent=self.NETWORK,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        
        self.addOutput(OutputVector(self.OUTPUT, self.tr('Main Drain')))


    def processAlgorithm(self, progress):

        network = dataobjects.getObjectFromUri(self.getParameterValue(self.NETWORK))
        cost_field = self.getParameterValue(self.COST_FIELD)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                network,
                QgsField('DP', QVariant.Int, len=2)
            ),
            network.dataProvider().geometryType(),
            network.crs())

        progress.setText(self.tr('Build Upward Index ...'))

        # forwardtracks = { nb: list(segment, na, cost) }
        forwardtracks = defaultdict(list)
        total = 100.0 / network.featureCount()
        anodes = set()

        for current, feature in enumerate(network.getFeatures()):

            toi = feature.attribute('TOI')
            if toi == 0:
                continue

            a = feature.attribute('NODE_A')
            b = feature.attribute('NODE_B')
            cost = feature.attribute(cost_field)

            forwardtracks[b].append((feature.id(), a, cost))
            anodes.add(a)

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Walk up from Outlets to Sources ...'))

        # backtracks = { ba: segment, nb, cost }
        backtracks = dict()
        sources = list()
        stack = list(set(forwardtracks.keys()) - anodes)
        del anodes

        while stack:

            nb = stack.pop()

            if backtracks.has_key(nb):
                sb, nbb, cost = backtracks[nb]
            else:
                cost = 0.0

            for segment, na, step_cost in forwardtracks[nb]:

                new_cost = cost + step_cost

                if backtracks.has_key(na):

                    sa, nba, costa = backtracks[na]
                    if new_cost < costa:
                        backtracks[na] = (segment, nb, new_cost)

                else:
                    
                    backtracks[na] = (segment, nb, new_cost)

                    if forwardtracks.has_key(na):
                        stack.append(na)
                    else:
                        sources.append(na)

        progress.setText(self.tr('Mark main drain ...'))
        total = 100.0 / network.featureCount()
        current = 0
        seen_segments = set()

        for source in sources:

            na = source

            while backtracks.has_key(na):
            
                segment, nb, cost = backtracks[na]

                if segment not in seen_segments:

                    feature = network.getFeatures(QgsFeatureRequest(segment)).next()
                    
                    out_feature = QgsFeature()
                    out_feature.setGeometry(feature.geometry())
                    out_feature.setAttributes(feature.attributes() + [
                            1
                        ])
                    writer.addFeature(out_feature)

                    seen_segments.add(segment)

                    current = current + 1
                    progress.setPercentage(int(current * total))

                na = nb

        progress.setText(self.tr('Output unmatched segments ...'))

        for feature in network.getFeatures():

            if feature.id() not in seen_segments:

                out_feature = QgsFeature()
                out_feature.setGeometry(feature.geometry())
                out_feature.setAttributes(feature.attributes() + [
                        0
                    ])
                writer.addFeature(out_feature)

                seen_segments.add(segment)
                current = current + 1
                progress.setPercentage(int(current * total))



