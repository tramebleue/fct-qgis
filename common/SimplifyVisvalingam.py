# -*- coding: utf-8 -*-

"""
***************************************************************************
    SimplifyVisvalingam.py
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
from visvalingam import simplify

def simplify_linestring(linestring, tolerance):

    return [ QgsPoint(x, y) for x, y in simplify([ (p.x(), p.y()) for p in linestring ], tolerance) ]

def simplify_geometry(geom, tolerance):

    if geom.isMultipart():

        if geom.type() == QGis.Line:

            return QgsGeometry.fromMultiPolyline([ simplify_linestring(line, tolerance) for line in geom.asMultiPolyline() ])

        elif geom.type() == QGis.Polygon:


            return QgsGeometry.fromMultiPolygon([[ simplify_linestring(ring, tolerance) for ring in part ] for part in geom.asMultiPolygon() ])

    else:

        if geom.type() == QGis.Line:

            return QgsGeometry.fromPolyline(simplify_linestring(geom.asPolyline(), tolerance))

        elif geom.type() == QGis.Polygon:

            return QgsGeometry.fromPolygon([ simplify_linestring(ring, tolerance) for ring in geom.asPolygon() ])

class SimplifyVisvalingam(GeoAlgorithm):

    INPUT = 'INPUT'
    TOLERANCE = 'TOLERANCE'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Simplify (Visvalingam Algorithm)')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Layer'), [ParameterVector.VECTOR_TYPE_LINE, ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addParameter(ParameterNumber(self.TOLERANCE,
                                          self.tr('Tolerance'),
                                          minValue=0.0, default=200.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Simplified')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        tolerance = self.getParameterValue(self.TOLERANCE)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList(),
            layer.dataProvider().geometryType(),
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        for current, feature in enumerate(features):

            simplified_geometry = simplify_geometry(feature.geometry(), tolerance)

            outfeature = QgsFeature()
            outfeature.setGeometry(simplified_geometry)
            outfeature.setAttributes(feature.attributes())
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))