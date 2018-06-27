# -*- coding: utf-8 -*-

"""
***************************************************************************
    PointOnSurface.py
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

def avg(a, b):
    return (a + b) / 2.0

class BisectorFinder(object):

    def __init__(self, polygon):

        bbox = polygon.boundingBox()
        self.loY = bbox.yMinimum()
        self.hiY = bbox.yMaximum()
        self.centreY = avg(self.loY, self.hiY)
        self.polygon = polygon

    def updateInterval(self, y):

        if y <= self.centreY:
            if y > self.loY:
                self.loY = y
        elif y < self.hiY:
            self.hiY = y

    def y(self):

        for ring in self.polygon.asPolygon():
            for x, y in ring:
                self.updateInterval(y)

        return avg(self.loY, self.hiY)


def geos_pos_simple(polygon):

    bbox = polygon.boundingBox()
    y = BisectorFinder(polygon).y()

    bisector = QgsGeometry.fromPolyline([
            QgsPoint(bbox.xMinimum(), y),
            QgsPoint(bbox.xMaximum(), y)
        ])
    
    if bisector.length() == 0.0:

        return bisector.vertexAt(0), 0.0
    
    else:
    
        hline = polygon.intersection(bisector)
        if hline.isMultipart():
            width = 0
            for start, stop in hline.asMultiPolyline():
                d = QgsPoint(*start).sqrDist(QgsPoint(*stop))
                if d > width:
                    width = d
                    x = avg(start[0], stop[0])
        else:

            start, stop  = hline.asPolyline()
            width = hline.length()
            x = avg(start[0], stop[0])

    return QgsPoint(x, y), width


def geos_point_on_surface(polygon):
    """ Returns a point that is guaranteed to lie on the surface,
    like PostGIS's ST_PointOnSurface()

    Implementation adapted from GEOS
    https://github.com/OSGeo/geos/blob/master/src/algorithm/InteriorPointArea.cpp
    (LGPL licensed)
    """

    if polygon.isMultipart():
    
        found = False
        max_width = 0
        pos = None
    
        for part in polygon.asMultiPolygon():

            poly = QgsGeometry.fromPolygon(part)
            pt, width = geos_pos_simple(poly)
            if not found or width > max_width:
                pos = pt
                max_width = width
                found = True
    
    else:

        pos, width = geos_pos_simple(polygon)
    
    return QgsGeometry.fromPoint(pos)


def point_on_surface(polygon):
    """ Returns a point that is guaranteed to lie on the surface,
    like PostGIS's ST_PointOnSurface()

    Implementation adapted from
    https://github.com/zsiki/realcentroid/blob/master/realcentroid_algorithm.py
    (GPL licensed)
    """

    pos = polygon.centroid()
    
    if not polygon.contains(pos):

        x, y = pos.asPoint()
        bbox = polygon.boundingBox()
        hline = QgsGeometry.fromPolyline([
                QgsPoint(bbox.xMinimum(), y),
                QgsPoint(bbox.xMaximum(), y)
            ]).intersection(polygon)
        
        if hline.isMultipart():

            # Find longest part middle point
            l = 0
            for start, stop in hline.asMultiPolyline():
                d = QgsPoint(*start).sqrDist(QgsPoint(*stop))
                if d > l:
                    l = d
                    x =  avg(start[0], stop[0])
                    # y =  avg(start[1], stop[1])
        
        else:
        
            start, stop = hline.asPolyline()
            x =  avg(start[0], stop[0])
            # y =  avg(start[1], stop[1])

        pos = QgsGeometry.fromPoint(QgsPoint(x, y))

    return pos


class PointOnSurface(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    OUTPUT_LAYER = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Point On Surface')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Polygon Layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Points On Surface')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            layer.fields().toList(),
            QGis.WKBPoint,
            layer.crs())
        
        total = 100.0 / layer.featureCount()
        for current, feature in enumerate(layer.getFeatures()):

            outfeature = QgsFeature()
            outfeature.setAttributes(feature.attributes())
            outfeature.setGeometry(feature.geometry().pointOnSurface())
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))