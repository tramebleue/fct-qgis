# -*- coding: utf-8 -*-

"""
***************************************************************************
    TrianglesToEdges.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
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

class TrianglesToEdges(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'
    POINTA_FIELD = 'POINTA'
    POINTB_FIELD = 'POINTB'
    POINTC_FIELD = 'POINTC'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Triangles To Edges')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Triangles'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Edges')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            [
                QgsField('GID', type=QVariant.Int, len=10),
                QgsField('NODE_A', type=QVariant.Int, len=10),
                QgsField('NODE_B', type=QVariant.Int, len=10)
            ],
            QGis.WKBLineString,
            layer.crs())

        total = 100.0 / layer.featureCount()
        seen_edges = set()
        fid = 0

        for current, feature in enumerate(layer.getFeatures()):

            triangle = feature.geometry().asPolygon()[0]
            assert(len(triangle) == 4)

            nodes = [ (feature.attribute(field) , triangle[i])
                      for i, field in enumerate([ self.POINTA_FIELD, self.POINTB_FIELD, self.POINTC_FIELD, self.POINTA_FIELD ]) ]

            it = iter(nodes)
            id0, p0 = next(it)

            for id1, p1 in it:

                minid, maxid = min(id0, id1), max(id0, id1)

                if not (minid, maxid) in seen_edges:

                    outfeature = QgsFeature()
                    outfeature.setGeometry(QgsGeometry.fromPolyline([ p0, p1 ]))
                    outfeature.setAttributes([
                            fid,
                            id0,
                            id1
                        ])
                    writer.addFeature(outfeature)
                    seen_edges.add((minid, maxid))
                    fid = fid + 1

                id0, p0 = id1, p1

            progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Created %d line features" % fid)