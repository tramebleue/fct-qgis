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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsField
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from shapely.wkb import loads
from shapely.ops import unary_union


class FastFixedDistanceBuffer(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    DISTANCE = 'DISTANCE'
    DISSOLVE = 'DISSOLVE'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Fast Fixed Distance Buffer')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_ANY]))
        self.addParameter(ParameterNumber(self.DISTANCE,
                                              self.tr('Fixed distance'), default=0.0))
        self.addParameter(ParameterBoolean(self.DISSOLVE,
                                           self.tr('Dissolve'), default=True))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Buffer')))

    def processAlgorithm(self, progress):

        dissolve = self.getParameterValue(self.DISSOLVE)
        distance = self.getParameterValue(self.DISTANCE)
        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))

        if dissolve:
            fields = [ QgsField('gid', type=QVariant.Int, len=10) ]
        else:
            fields = layer.pendingFields()
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields, QGis.WKBPolygon, layer.crs())

        features = vector.features(layer)
        items = []
        total = 100.0 / len(features)

        progress.setText(self.tr("Compute feature-wise buffers ..."))
        for current, feature in enumerate(features):

            geom = loads(feature.geometry().asWkb())
            buf = geom.buffer(distance)

            if not dissolve:
                outFeature = QgsFeature()
                qgeom = QgsGeometry()
                qgeom.fromWkb(buf.to_wkb())
                outFeature.setGeometry(qgeom)
                outFeature.setAttributes(feature.attributes())
                writer.addFeature(outFeature)
            else:
                items.append(buf)

            progress.setPercentage(int(current * total))

        if dissolve:

            progress.setText(self.tr("Dissolve objects ..."))
            union = unary_union(items)
            qgeom = QgsGeometry()
            qgeom.fromWkb(union.to_wkb())
            if qgeom.wkbType() == QGis.WKBPolygon:
                outFeature = QgsFeature()
                outFeature.setGeometry(qgeom)
                outFeature.setAttributes([ 1L ])
                writer.addFeature(outFeature)
            elif qgeom.wkbType() == QGis.WKBMultiPolygon:
                polygons = qgeom.asMultiPolygon()
                for i, polygon in enumerate(polygons):
                    geom = QgsGeometry.fromPolygon(polygon)
                    outFeature = QgsFeature()
                    outFeature.setGeometry(geom)
                    outFeature.setAttributes([ i ])
                    writer.addFeature(outFeature)

        progress.setText(self.tr("Done."))
