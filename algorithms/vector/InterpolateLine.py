# -*- coding: utf-8 -*-

"""
***************************************************************************
    InterpolateLine.py
    ---------------------
    Date                 : February 2018
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

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

from ...core import vector as vector_helper

from math import sqrt, floor
import numpy as np

def catmullrom_interpolator(alpha):
  
    # Centripetal Catmull–Rom spline
    # https://en.wikipedia.org/wiki/Centripetal_Catmull%E2%80%93Rom_spline
    # n-dim implementation

    def tj(ti, pi, pj):
        v = np.array([ pi, pj ])
        return float(np.power(np.sqrt(np.sum(np.square(v[:, 1] - v[:, 0]))), alpha))

    def interpolator(t, p0, p1, p2, p3):
  
        t0 = 0
        t1 = tj(t0, p0, p1)
        t2 = tj(t1, p1, p2)
        t3 = tj(t2, p2, p3)
        tx = t1 + t*(t2 - t1)
    
        def coord(k):
    
            x0 = p0[k]
            x1 = p1[k]
            x2 = p2[k]
            x3 = p3[k]

            a1 = (t1-tx)/(t1-t0)*x0 + (tx-t0)/(t1-t0)*x1
            a2 = (t2-tx)/(t2-t1)*x1 + (tx-t1)/(t2-t1)*x2
            a3 = (t3-tx)/(t3-t2)*x2 + (tx-t2)/(t3-t2)*x3
            b1 = (t2-tx)/(t2-t0)*a1 + (tx-t0)/(t2-t0)*a2
            b2 = (t3-tx)/(t3-t1)*a2 + (tx-t1)/(t3-t1)*a3

            return (t2-tx)/(t2-t1)*b1 + (tx-t1)/(t2-t1)*b2

        return [ coord(i) for i in range(len(p0)) ]

    return interpolator 


class InterpolateLine(GeoAlgorithm):

    INPUT = 'INPUT'
    DELTAY = 'DELTAY'
    INTERPOLATION_DISTANCE = 'INTERPOLATION_DISTANCE'
    ALPHA = 'ALPHA'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Interpolate Line')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Points'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterNumber(self.INTERPOLATION_DISTANCE,
                                          self.tr('Interpolation Distance'),
                                          minValue=0.0, default=50.0))
        
        self.addParameter(ParameterNumber(self.DELTAY,
                                          self.tr('Exaggeration'),
                                          minValue=0.0, default=20.0))

        self.addParameter(ParameterNumber(self.ALPHA,
                                          self.tr('Alpha'),
                                          minValue=0.0, default=0.5, maxValue=1.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Interpolated Line')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        dx = self.getParameterValue(self.INTERPOLATION_DISTANCE)
        dy = self.getParameterValue(self.DELTAY)
        alpha = self.getParameterValue(self.ALPHA)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            [],
            # QgsField('GID', QVariant.Int, len=10)
            QGis.WKBLineString,
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)
        fid = 0

        points = list()

        def exaggerate(y):

            if y < 0:
                return y - dy
            else:
                return y + dy

        for current, feature in enumerate(features):

            point = feature.geometry().asPoint()
            points.append([ point.x(), exaggerate(point.y()) ])

            progress.setPercentage(int(current * total))

        points.sort(key=lambda p: p[0])

        # def emit(c):

        #     geom = QgsGeometry.fromPoint(QgsPoint(*c))
        #     feature = QgsFeature()
        #     feature.setGeometry(geom)
        #     # feature.setAttributes([ 0 ])
        #     writer.addFeature(feature)

        interpolate = catmullrom_interpolator(alpha)
        coordinates = list()

        for k in xrange(len(points) - 3):

            p0 = points[k]
            p1 = points[k+1]
            p2 = points[k+2]
            p3 = points[k+3]
            length = sqrt((p2[1] - p1[1])**2 + (p2[0] - p1[0])**2)

            if length > 0.0:
            
                step = dx / length

                for t in np.arange(0, 1, step):

                    c = interpolate(t, p0, p1, p2, p3)
                    coordinates.append(QgsPoint(*c))

        geom = QgsGeometry.fromPolyline(coordinates)
        feature = QgsFeature()
        feature.setGeometry(geom)
        writer.addFeature(feature)


