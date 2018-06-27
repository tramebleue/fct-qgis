# -*- coding: utf-8 -*-

"""
***************************************************************************
    MeasureDGO.py
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
__date__ = 'June 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

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

from collections import defaultdict
from math import sqrt
import numpy as np

class MeasureDGO(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    DGO_PK_FIELD = 'DGO_PK'
    AXIS_FIELD = 'AXIS'
    MEASURE_FIELD = 'MEASURE'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Polygon Linear Referencing')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Intersection between Linear Reference and Polygon'),
                                          [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.DGO_PK_FIELD,
                                              self.tr('DGO Primary Key'),
                                              parent=self.INPUT_LAYER,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.AXIS_FIELD,
                                              self.tr('Axis Field'),
                                              parent=self.INPUT_LAYER,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                              self.tr('Measure Field'),
                                              parent=self.INPUT_LAYER,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Measured Linear Location')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        oid_field = self.getParameterValue(self.DGO_PK_FIELD)
        pathid_field = self.getParameterValue(self.AXIS_FIELD)
        meas_field = self.getParameterValue(self.MEASURE_FIELD)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.fields().toList(),
            QGis.WKBPoint,
            layer.crs())

        progress.setText(self.tr('Build layer index on field %s' % oid_field))
        features = vector.features(layer)
        total = 100.0 / len(features)
        index = defaultdict(list)

        for current, feature in enumerate(features):

            oid = feature.attribute(oid_field)
            index[oid].append(feature.id())

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Locate Object on Linear Reference'))
        total = 100.0 / len(index.keys())
        progress.setPercentage(0)

        for current, oid in enumerate(index.keys()):

            segments = list()
            pathid = None

            for fid in index[oid]:

                feature = layer.getFeatures(QgsFeatureRequest(fid)).next()
                pid = feature.attribute(pathid_field)
                segments.append(feature)

                if pathid is None or pid < pathid:
                    pathid = pid

            def by_meas(a, b):

                meas_a = a.attribute(meas_field)
                meas_b = b.attribute(meas_field)
                
                if meas_a == meas_b:
                    return 0
                elif meas_a < meas_b:
                    return 1
                else:
                    return -1

            segments = filter(lambda f: f.attribute(pathid_field) == pathid, segments)
            segments.sort(by_meas)
            length = np.sum([ segment.geometry().length() for segment in segments ])

            i = 0
            s = 0.0

            while (s + segments[i].geometry().length()) < 0.5*length:
                s = s + segments[i].geometry().length()
                i = i + 1

            p = segments[i].geometry().interpolate(0.5*length - s)

            outfeature = QgsFeature()
            outfeature.setGeometry(p)
            outfeature.setAttributes(segments[i].attributes())
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))
