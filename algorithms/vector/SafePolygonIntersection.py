# -*- coding: utf-8 -*-

"""
***************************************************************************
    SafePolygonIntersection.py
    ---------------------
    Date                 : April 2018
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

from qgis.core import QGis, QgsFeatureRequest, QgsFeature, QgsGeometry, QgsWKBTypes

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.ProcessingLog import ProcessingLog
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.core.parameters import ParameterVector
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector

class SafePolygonIntersection(GeoAlgorithm):

    INPUT = 'INPUT'
    INPUT2 = 'INPUT2'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Safe Polygon Intersection')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterVector(self.INPUT2,
                                          self.tr('Intersect layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Intersection')))

    def processAlgorithm(self, progress):

        vlayerA = dataobjects.getObjectFromUri(
            self.getParameterValue(self.INPUT))
        vlayerB = dataobjects.getObjectFromUri(
            self.getParameterValue(self.INPUT2))

        geomType = QGis.multiType(vlayerA.wkbType())
        fields = vector.combineVectorFields(vlayerA, vlayerB)
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(fields,
                                                                     geomType, vlayerA.crs())
        
        progress.setText('Build Intersect layer index ...')
        index = vector.spatialindex(vlayerB)


        progress.setText('Intersect polygons ...')
        selectionA = vector.features(vlayerA)
        total = 100.0 / len(selectionA)
        errors = 0

        for current, feature in enumerate(selectionA):

            for intersector_fid in index.intersects(feature.geometry().boundingBox()):

                intersector = vlayerB.getFeatures(QgsFeatureRequest(intersector_fid)).next()

                def outputPolygon(geometry):

                    out_feature = QgsFeature()
                    out_feature.setGeometry(geometry)
                    out_feature.setAttributes(
                        feature.attributes() + intersector.attributes()
                    )
                    writer.addFeature(out_feature)

                def processGeometry(geometry):

                    if geometry.type() == QGis.Polygon:

                        if geometry.isMultipart():

                            for part in geometry.asMultiPolygon():

                                outputPolygon(QgsGeometry.fromPolygon(part))

                        else:

                            outputPolygon(geometry)

                try:

                    if feature.geometry().intersects(intersector.geometry()):

                        intersection = feature.geometry().intersection(intersector.geometry())

                        if QgsWKBTypes.flatType(intersection.geometry().wkbType()) == QgsWKBTypes.GeometryCollection:

                            for geometry in intersection.asGeometryCollection():

                               processGeometry(geometry)

                        else:

                            processGeometry(intersection)

                except:
                    
                    errors = errors + 1

                progress.setPercentage(int(current * total))

        if errors:

            ProcessingLog.addToLog(ProcessingLog.LOG_WARNING, "%d errors encoutered" % errors)