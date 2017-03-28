# -*- coding: utf-8 -*-

"""
***************************************************************************
    SplitLine.py
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
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from math import sqrt


class Sequencing(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    UNMATCHED_LAYER = 'UNMATCHED_LAYER'
    GID_FIELD = 'GID_FIELD'
    ORIGIN_GID = 'ORIGIN_GID'
    PRECISION = 'PRECISION'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Sequencing')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterTableField(self.GID_FIELD,
                                              self.tr('Primary key field'), self.INPUT_LAYER))
        self.addParameter(ParameterNumber(self.ORIGIN_GID,
                                          self.tr('Origin Feature PKID'), default=1, optional=False))
        self.addParameter(ParameterNumber(self.PRECISION,
                                          self.tr('precision'), default=1.0, optional=False))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Ordered graph')))
        self.addOutput(OutputVector(self.UNMATCHED_LAYER, self.tr('Unmatched lines')))

    def asPolyline(self, geometry):
        if geometry.isMultipart():
            return geometry.asMultiPolyline()[0]
        else:
            return geometry.asPolyline()

    def snapToPrecision(self, point, precision):
        x = round(point.x() / precision, 0) * precision
        y = round(point.y() / precision, 0) * precision
        return QgsPoint(x, y)

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        origin_gid = self.getParameterValue(self.ORIGIN_GID)
        origin_id = None
        precision = self.getParameterValue(self.PRECISION)

        layerFields = layer.fields()
        fields = layerFields.toList() + [
            QgsField('ORDER', type=QVariant.Int, len=10),
            QgsField('STARTM', type=QVariant.Double, len=12, prec=4),
            QgsField('ENDM', type=QVariant.Double, len=12, prec=4)
        ]
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields, layer.dataProvider().geometryType(), layer.crs())

        progress.setText(self.tr("Build spatial index ..."))
        index = QgsSpatialIndex(layer.getFeatures())

        features = vector.features(layer)
        total = 100.0 / (2*len(features))
        links = dict()

        progress.setText(self.tr("Match segments by endpoints ..."))
        for current, feature in enumerate(features):

            nearest = None
            distance = float('inf')
            geometry = feature.geometry()
            polyline = self.asPolyline(geometry)
            
            start_point = self.snapToPrecision(polyline[0], precision)
            start_links = []
            nearests = index.nearestNeighbor(start_point, 5)
            q = QgsFeatureRequest().setFilterFids(nearests)
            for candidate in layer.getFeatures(q):
                canidate_polyline = self.asPolyline(candidate.geometry())
                if (start_point == self.snapToPrecision(canidate_polyline[0], precision)) or (start_point == self.snapToPrecision(canidate_polyline[-1], precision)):
                    start_links.append(candidate.id())

            end_point = self.snapToPrecision(polyline[-1], precision)
            end_links = []
            nearests = index.nearestNeighbor(end_point, 5)
            q = QgsFeatureRequest().setFilterFids(nearests)
            for candidate in layer.getFeatures(q):
                canidate_polyline = self.asPolyline(candidate.geometry())
                if (end_point == self.snapToPrecision(canidate_polyline[0], precision)) or (end_point == self.snapToPrecision(canidate_polyline[-1], precision)):
                    end_links.append(candidate.id())

            links[feature.id()] = (start_links, end_links)
            if feature.attribute(self.getParameterValue(self.GID_FIELD)) == origin_gid:
                origin_id = feature.id()
                ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Origin FID %s" % origin_id)

            progress.setPercentage(int(current * total))

        assert(origin_id != None)
        pending_stack = [ origin_id ]
        measures = dict()

        progress.setText(self.tr("Build directed graph and compute measures ..."))
        while pending_stack:
            
            next_key = pending_stack.pop()
            if not links.has_key(next_key):
                continue

            start_links, end_links = links.pop(next_key)
            next_feature = layer.getFeatures(QgsFeatureRequest(next_key)).next()
            
            pending_stack = start_links + end_links + pending_stack
            
            connection = None
            for link_id in start_links + end_links:
                if measures.has_key(link_id):
                    connection = link_id
                    break
            if connection:
                connection_measure = measures[connection]
                measure = [
                    connection_measure[0] + 1,
                    connection_measure[2],
                    connection_measure[2] + next_feature.geometry().length()
                ]
            else:
                measure = [
                    1L,
                    0.0,
                    next_feature.geometry().length()
                ]
            measures[next_key] = measure
            
            outFeature = QgsFeature()
            outFeature.setGeometry(next_feature.geometry())
            outFeature.setAttributes(next_feature.attributes() + measure)
            writer.addFeature(outFeature)
            current = current + 1
            progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "%d unmatched lines" % len(links))
        progress.setText(self.tr("Output unmatched lines ..."))
        writer = self.getOutputFromName(self.UNMATCHED_LAYER).getVectorWriter(
            layerFields, layer.dataProvider().geometryType(), layer.crs())
        for next_key in links.keys():
            next_feature = layer.getFeatures(QgsFeatureRequest(next_key)).next()
            outFeature = QgsFeature()
            outFeature.setGeometry(next_feature.geometry())
            outFeature.setAttributes(next_feature.attributes())
            writer.addFeature(outFeature)
            current = current + 1
            progress.setPercentage(int(current * total))

        progress.setText(self.tr("Done."))

