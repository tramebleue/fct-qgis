# -*- coding: utf-8 -*-

"""
***************************************************************************
    DeduplicateLines.py
    ---------------------
    Date                 : August 2018
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
__date__ = 'August 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsField
from PyQt4.QtCore import QVariant
import processing
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

import numpy as np
from collections import defaultdict
from ...core.topology import Arc, cut, dedup

def arc_geometry(coordinates, arc):

    a = arc.a
    b = arc.b

    if a > b:
        return QgsGeometry.fromPolyline([ QgsPoint(x,y) for x, y in np.flip(coordinates[b:a+1], 0) ])
    else:
        return QgsGeometry.fromPolyline([ QgsPoint(x,y) for x, y in coordinates[a:b+1] ])

class DeduplicateLines(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    QUANTIZATION = 'QUANTIZATION'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Deduplicate Lines')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterNumber(self.QUANTIZATION,
                                          self.tr('Quantization'),
                                          minValue=0, default=1e6))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Deduplicated')))

    def processAlgorithm(self, progress):

        layer = processing.getObject(self.getParameterValue(self.INPUT))
        quantization = self.getParameterValue(self.QUANTIZATION)

        writer = writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            [
                QgsField('ARCID', QVariant.Int, len=9),
                QgsField('COUNT', QVariant.Int, len=5)
            ],
            QGis.WKBLineString,
            layer.crs())

        progress.setText(self.tr('Read input features ...'))

        features = vector.features(layer)
        total = 100.0 / len(features)

        coordinates = list()
        lines = list()

        def extract_line(line_coords):

            a = len(coordinates)
            coordinates.extend(map(tuple, line_coords))
            b = len(coordinates) - 1

            arc = Arc(a, b)
            lines.append(arc)

            return arc

        for current, feature in enumerate(features):

            geom = feature.geometry()

            if geom.isMultipart():

                for line_coords in geom.asMultiPolyline():
                    extract_line(line_coords)

            else:

                line_coords = geom.asPolyline()
                extract_line(line_coords)
                
            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Deduplicate geometries ...'))

        coordinates = np.array(coordinates)
        rings = lines
        lines = list()

        minx = np.min(coordinates[:, 0])
        miny = np.min(coordinates[:, 1])
        maxx = np.max(coordinates[:, 0])
        maxy = np.max(coordinates[:, 1])

        if quantization > 1:
            kx = (minx == maxx) and 1 or (maxx - minx)
            ky = (miny == maxy) and 1 or (maxy - miny)
            quantized = np.int32(np.round((coordinates - (minx, miny)) / (kx, ky) * quantization))
        else:
            kx = ky = 1
            quantized = coordinates

        cut(quantized, lines, rings)
        arcs = dedup(quantized, lines, rings)
        arc_index = { (arc.a, arc.b): arc for arc in arcs }

        progress.setText('Count arc repetitions ...')

        for ring in rings:

            current = ring
            while current:

                start = current.a
                end   = current.b

                if start > end:

                    arc = arc_index[(end, start)]

                else:

                    arc = arc_index[(start, end)]

                arc.count += 1
                current = current.next

        progress.setText('%d rings / %d arcs' % (len(rings), len(arcs)))
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, '%d rings / %d arcs' % (len(rings), len(arcs)))
        progress.setText(self.tr('Output deduplicated lines ...'))

        if quantization > 1:
            coordinates = quantized * (kx / quantization, ky / quantization) + (minx, miny)

        total = 100.0 / len(arcs)

        for current, arc in enumerate(arcs):

            geom = arc_geometry(coordinates, arc)
            out_feature = QgsFeature()
            out_feature.setGeometry(geom)
            out_feature.setAttributes([
                    current,
                    arc.count
                ])
            writer.addFeature(out_feature)

            progress.setPercentage(int(current * total))