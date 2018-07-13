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

def hausdorff_distance(source_geom, target_geom):

    if source_geom.isMultipart():
        points = [ p for line in source_geom.asMultiPolyline() for p in line ]
    else:
        points = source_geom.asPolyline()

    return max([ target_geom.distance(QgsGeometry.fromPoint(p)) for p in points ])

class MatchNearestLineUpdate(GeoAlgorithm):

    INPUT = 'INPUT'
    TARGET = 'TARGET'
    TARGET_PK = 'TARGET_PK'
    MATCHING_FK_FIELD = 'MATCHING_FK_FIELD'
    MATCH_DISTANCE_FIELD = 'MATCH_DISTANCE_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Match Nearest Line (Update Selected)')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Lines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.MATCHING_FK_FIELD,
                                              self.tr('Target FK Field'),
                                              parent=self.INPUT,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.MATCH_DISTANCE_FIELD,
                                              self.tr('Match Distance Field'),
                                              parent=self.INPUT,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.TARGET,
                                          self.tr('Target Lines'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.TARGET_PK,
                                              self.tr('Target Primary Key'),
                                              parent=self.TARGET,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Matched Lines')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        target = dataobjects.getObjectFromUri(self.getParameterValue(self.TARGET))
        pk_field = self.getParameterValue(self.TARGET_PK)
        matching_fk_field = self.getParameterValue(self.MATCHING_FK_FIELD)
        match_distance_field = self.getParameterValue(self.MATCH_DISTANCE_FIELD)

        writer =  self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList(),
            layer.dataProvider().geometryType(),
            layer.crs())

        matching_fk_field_idx = vector.resolveFieldIndex(layer, matching_fk_field)
        match_distance_field_idx = vector.resolveFieldIndex(layer, match_distance_field)

        target_index = QgsSpatialIndex(target.getFeatures())
        features = vector.features(layer)
        total = 100.0 / layer.featureCount()

        selected = layer.selectedFeaturesIds()

        for current, feature in enumerate(layer.getFeatures()):

            geom = feature.geometry()
            attributes = feature.attributes()

            if feature.id() in selected:

                midpoint = geom.interpolate(0.5 * geom.length())
                # search_box = feature.geometry().boundingBox()
                # search_box.grow(max_distance)

                min_distance = float('inf')
                matching_pk = None

                for fid in target_index.nearestNeighbor(midpoint.asPoint(), 10):

                    candidate = target.getFeatures(QgsFeatureRequest(fid)).next()
                    # d = midpoint.distance(candidate.geometry())
                    d = hausdorff_distance(geom, candidate.geometry())
                    
                    if d < min_distance:

                        min_distance = d
                        matching_pk = candidate.attribute(pk_field)

                attributes[matching_fk_field_idx] = matching_pk
                attributes[match_distance_field_idx] = min_distance

            out_feature = QgsFeature()
            out_feature.setGeometry(geom)
            out_feature.setAttributes(attributes)
            writer.addFeature(out_feature)

            progress.setPercentage(int(current * total))