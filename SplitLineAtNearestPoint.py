# -*- coding: utf-8 -*-

"""
***************************************************************************
    SplitLineAtNearestPoint.py
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

from PyQt4.QtCore import QVariant
from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from qgis.core import QgsFields, QgsField, QgsFeatureRequest, QgsExpression
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog
from collections import defaultdict

class SplitLineAtNearestPoint(GeoAlgorithm):

    INPUT = 'INPUT'
    NEAR_TABLE = 'NEAR_TABLE'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Split Line At Nearest Point')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input lines'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.NEAR_TABLE,
                                          self.tr('Near table'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Splitted lines')))

    def processAlgorithm(self, progress):

        ID_FIELD = 'FID'

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        near_table = dataobjects.getObjectFromUri(self.getParameterValue(self.NEAR_TABLE))
        fields = QgsFields(layer.pendingFields())
        fields.append(QgsField('UGO_ID', QVariant.Int))
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            fields.toList(), layer.dataProvider().geometryType(), layer.crs())

        # line_id -> list of vertex index to split at
        split_records = defaultdict(list)

        for split_feature in vector.features(near_table):
            near_id = split_feature.attribute('NEAR_ID')
            query = QgsFeatureRequest(QgsExpression('%s = %d' % (ID_FIELD, near_id)))
            near_feature = layer.getFeatures(query).next()
            if near_feature:
                snap, at_vertex, before_vertex, after_vertex, sq_distance = \
                    near_feature.geometry().closestVertex(split_feature.geometry().asPoint())
                split_records[near_id].append(at_vertex)

        lines = len(split_records.keys())
        splits = 0

        for fid, vertices in split_records.items():
            query = QgsFeatureRequest(QgsExpression('%s = %d' % (ID_FIELD, fid)))
            feature = layer.getFeatures(query).next()
            points = feature.geometry().asPolyline()
            vertices.sort()
            vertices.append(len(points)-1)
            current_vertex = 0
            for n, vertex in enumerate(vertices):
                if not vertex > current_vertex:
                    continue
                part = points[current_vertex:vertex]
                newFeature = QgsFeature()
                newFeature.setFields(fields)
                self.copyAttributes(feature, newFeature)
                newFeature.setAttribute('UGO_ID', n)
                newFeature.setGeometry(QgsGeometry.fromPolyline(part))
                writer.addFeature(newFeature)
                current_vertex = vertex
                splits += 1

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Splitted %d lines into %d smaller lines' % (lines, splits))

    def copyAttributes(self, src, dst):
        for field in src.fields():
            dst.setAttribute(field.name(), src.attribute(field.name()))
