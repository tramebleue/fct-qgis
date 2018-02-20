# -*- coding: utf-8 -*-

"""
***************************************************************************
    RandomPoints.py
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
from math import sqrt
from numpy.random import uniform

class RandomPoints(GeoAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    INPUT_FID_FIELD = 'INPUT_FID_FIELD'
    ZOI_LAYER = 'ZOI_LAYER'
    ZOI_FID_FIELD = 'ZOI_FID_FIELD'
    NUM_SAMPLES = 'NUM_SAMPLES'
    MIN_DISTANCE = 'MIN_DISTANCE'
    OUTPUT_LAYER = 'OUTPUT_LAYER'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Random Points')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Sample Layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        
        self.addParameter(ParameterTableField(self.INPUT_FID_FIELD,
                                          self.tr('Sample Id Field'),
                                          parent=self.INPUT_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_ANY))

        self.addParameter(ParameterVector(self.ZOI_LAYER,
                                          self.tr('Zone Of Interest'), [ParameterVector.VECTOR_TYPE_POLYGON],
                                          optional=True))

        self.addParameter(ParameterTableField(self.ZOI_FID_FIELD,
                                          self.tr('ZOI Id Field'),
                                          parent=self.ZOI_LAYER,
                                          datatype=ParameterTableField.DATA_TYPE_ANY,
                                          optional=True))

        self.addParameter(ParameterNumber(self.NUM_SAMPLES,
                                          self.tr('Number of points'),
                                          default=100, minValue=0, optional=False))

        self.addParameter(ParameterNumber(self.MIN_DISTANCE,
                                          self.tr('Minimum Distance Between Points'),
                                          default=0.0, minValue=0.0, optional=True))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Random Points')))


    def getLayerField(self, layer, fielname):

        idx = layer.fieldNameIndex(fielname)
        if idx != -1:
            return layer.fields().toList()[idx]
        else:
            return None

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        layer_fid_field = self.getParameterValue(self.INPUT_FID_FIELD)
        zoi_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.ZOI_LAYER))
        zoi_fid_field = self.getParameterValue(self.ZOI_FID_FIELD)
        num_samples = self.getParameterValue(self.NUM_SAMPLES)
        min_distance = self.getParameterValue(self.MIN_DISTANCE)

        if zoi_layer is None:

            ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Using input layer extent as ZOI")

            zoi_layer = QgsVectorLayer("Polygon", "zoi", "memory")
            zoi_layer.setCrs(layer.crs())
            zoi_layer.dataProvider().addAttributes([ QgsField('ZOID', QVariant.Int, len=10) ])
            zoi_fid_field = 'ZOID'
            
            zoi_layer.startEditing()
            zoi = QgsFeature()
            zoi.setAttributes([ 1 ])
            zoi.setGeometry(QgsGeometry.fromRect(layer.extent()))
            zoi_layer.addFeature(zoi)
            zoi_layer.commitChanges()

        progress.setText(self.tr("Build input index ..."))
        
        layer_index = QgsSpatialIndex()
        for feature in vector.features(layer):
            layer_index.insertFeature(feature)
        
        output_index = QgsSpatialIndex()

        outlayer = QgsVectorLayer("Point", "randompoints", "memory")
        outlayer.setCrs(layer.crs())
        outlayer.dataProvider().addAttributes([
                QgsField('FID', QVariant.Int, len=10),
                self.getLayerField(zoi_layer, zoi_fid_field),
                self.getLayerField(layer, layer_fid_field)
            ])

        def random_point_in_zoi(zoi):

            zoi_extent = zoi.geometry().boundingBox()
            
            # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Next candidate in FOI (%f, %f)" % (x, y))
            # return QgsGeometry.fromPoint(QgsPoint(x, y))

            while True:

                x = uniform(zoi_extent.xMinimum(), zoi_extent.xMaximum())
                y = uniform(zoi_extent.yMinimum(), zoi_extent.yMaximum())
                
                p = QgsGeometry.fromPoint(QgsPoint(x, y))
                
                if not zoi.geometry().contains(p):
                    continue
                else:
                    return p

        progress.setText(self.tr("Generate random points ..."))

        fid = 0
        outlayer.startEditing()
        zoi_cnt = zoi_layer.featureCount()

        for current, zoi in enumerate(vector.features(zoi_layer)):

            ProcessingLog.addToLog(ProcessingLog.LOG_INFO,
                "Processing feature %s (%d / %d)" % (
                    zoi.attribute(zoi_fid_field),
                    current + 1,
                    zoi_cnt))
            
            total = 100.0 / num_samples
            n = 0

            while n < num_samples:

                p = random_point_in_zoi(zoi)

                containing_feature = None
                for c in layer_index.intersects(p.boundingBox()):
                    
                    candidate = layer.getFeatures(QgsFeatureRequest(c)).next()
                    if candidate.geometry().contains(p):
                        containing_feature = candidate
                        break

                if containing_feature is None:
                    continue

                if min_distance > 0:

                    not_far_enough = False
                    for nearest_id in output_index.nearestNeighbor(p.asPoint(), 1):
                        nearest = outlayer.getFeatures(QgsFeatureRequest(nearest_id)).next()
                        if nearest.geometry().distance(p) < min_distance:
                            not_far_enough = True
                            break        

                    if not_far_enough:
                        continue

                outfeature = QgsFeature()
                outfeature.setGeometry(p)
                outfeature.setAttributes([
                        fid,
                        zoi.attribute(zoi_fid_field),
                        containing_feature.attribute(layer_fid_field)
                    ])
                outlayer.addFeature(outfeature)
                output_index.insertFeature(outfeature)
                fid = fid + 1
                n = n + 1

                progress.setPercentage(int(n * total))

        outlayer.commitChanges()

        progress.setText(self.tr("Write output layer ..."))

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            outlayer.fields().toList(),
            outlayer.dataProvider().geometryType(),
            outlayer.crs())

        for feature in outlayer.getFeatures():
            writer.addFeature(feature)

