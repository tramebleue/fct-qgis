# -*- coding: utf-8 -*-

"""
SelectByDistance - Select vectors within a specific distance to layer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsApplication,
    QgsExpression,
    QgsGeometry,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes
)

from processing.algs.qgis.QgisAlgorithm import QgisAlgorithm # pylint:disable=import-error,no-name-in-module

from ..metadata import AlgorithmMetadata

class SelectByDistance(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Select vectors within a specific distance to layer
    """

    METADATA = AlgorithmMetadata.read(__file__, 'SelectByDistance')

    TARGET_LAYER = 'TARGET_LAYER'
    DISTANCE_TO_LAYER = 'DISTANCE_TO_LAYER'
    DISTANCE = 'DISTANCE'

    def initAlgorithm(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(self.TARGET_LAYER,
                                          self.tr('Select From Layer'), [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterFeatureSource(self.DISTANCE_TO_LAYER,
                                          self.tr('Distance To Layer'), [QgsProcessing.TypeVectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterDistance(self.DISTANCE,
                                          self.tr('Max Distance'),
                                          defaultValue=0.0))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        target_layer = self.parameterAsVectorLayer(parameters, self.TARGET_LAYER, context)
        distance_layer = self.parameterAsVectorLayer(parameters, self.DISTANCE_TO_LAYER, context)
        distance = self.parameterAsDouble(parameters,self.DISTANCE,context)

        spatial_index = QgsSpatialIndex(distance_layer.getFeatures())

        total = 100.0 / target_layer.featureCount() if target_layer.featureCount() else 0
        selection = set()

        for current, feature in enumerate(target_layer.getFeatures()):

            if feedback.isCanceled():
                break
            
            search_box = feature.geometry().boundingBox()
            search_box.grow(distance)
            
            for candid in spatial_index.intersects(search_box):

                s = context.getMapLayer(distance_layer.sourceName())
                candidate = s.getFeature(candid)

                if (feature.geometry().distance(candidate.geometry())) <= distance:
                    selection.add(feature.id())
                    break

            feedback.setProgress(int(current * total))

        target_layer.selectByIds(list(selection), QgsVectorLayer.SetSelection)

        return{}