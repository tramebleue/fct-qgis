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

from ...core import vector as vector_helper

from collections import defaultdict
from math import sqrt


class MatchNetworkNodes(GeoAlgorithm):

    SOURCE = 'SOURCE'
    TARGET = 'TARGET'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Match Network Nodes')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        self.addParameter(ParameterVector(self.SOURCE,
                                          self.tr('Source Nodes'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterVector(self.TARGET,
                                          self.tr('Target Nodes'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Paired Nodes')))

    def processAlgorithm(self, progress):

        max_neighbors = 10
        max_distance = 250.0

        source_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.SOURCE))
        target_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.TARGET))

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                source_layer,
                QgsField('LAYER', QVariant.Int, len=2),
                QgsField('PAIRID', QVariant.Int, len=10),
                QgsField('TX', QVariant.Double, len=10, prec=2),
                QgsField('TY', QVariant.Double, len=10, prec=2)
            ),
            source_layer.dataProvider().geometryType(),
            source_layer.crs())


        source_index = QgsSpatialIndex(source_layer.getFeatures())
        target_index = QgsSpatialIndex(target_layer.getFeatures())

        progress.setText(self.tr('Match source nodes'))
        total = 100.0 / source_layer.featureCount()
        source_match = dict()

        for current, feature in enumerate(source_layer.getFeatures()):

            geom = feature.geometry()
            p = geom.asPoint()
            ptype = feature.attribute('TYPE')
            distance = float('inf')
            pair = None

            for fid in target_index.nearestNeighbor(p, max_neighbors):

                f = target_layer.getFeatures(QgsFeatureRequest(fid)).next()
                d = f.geometry().distance(geom)
                
                # if (f.attribute('TYPE') == ptype or f.attribute('TYPE') == 'NODE') and d < distance:
                if d < distance:

                    distance = d
                    pair = fid

            if distance < max_distance:
                source_match[feature.id()] = pair
            else:
                source_match[feature.id()] = None

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Match target nodes'))
        total = 100.0 / target_layer.featureCount()
        target_match = dict()

        for current, feature in enumerate(target_layer.getFeatures()):

            geom = feature.geometry()
            p = geom.asPoint()
            ptype = feature.attribute('TYPE')
            distance = float('inf')
            pair = None

            for fid in source_index.nearestNeighbor(p, max_neighbors):

                f = source_layer.getFeatures(QgsFeatureRequest(fid)).next()
                d = f.geometry().distance(geom)
                
                # if (ptype == 'NODE' or f.attribute('TYPE') == ptype) and d < distance:
                if d < distance:

                    distance = d
                    pair = fid

            target_match[feature.id()] = pair

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Output source nodes'))
        # total = 100.0 / (source_layer.featureCount() + target_layer.featureCount())
        total = 100.0 / source_layer.featureCount()

        for current, feature in enumerate(source_layer.getFeatures()):

            if feature.attribute('TYPE') == 'NODE':
                continue

            match = source_match[feature.id()]

            if match is not None and target_match[match] == feature.id():

                target = target_layer.getFeatures(QgsFeatureRequest(match)).next()
                targetid = target.attribute('GID')
                p = target.geometry().asPoint()
                targetx = p.x()
                targety = p.y()

            else:

                targetid = None
                targetx = targety = None

            out_feature = QgsFeature()
            out_feature.setGeometry(feature.geometry())
            out_feature.setAttributes(feature.attributes() + [
                    0,
                    targetid,
                    targetx,
                    targety
                ])

            writer.addFeature(out_feature)
            progress.setPercentage(int(current * total))

        # progress.setText(self.tr('Output target nodes'))

        # for feature in target_layer.getFeatures():

        #     out_feature = QgsFeature()
        #     out_feature.setGeometry(feature.geometry())
        #     out_feature.setAttributes(feature.attributes() + [
        #             1,
        #             None,
        #             None,
        #             None
        #         ])

        #     current = current + 1
        #     writer.addFeature(out_feature)
        #     progress.setPercentage(int(current * total))
        