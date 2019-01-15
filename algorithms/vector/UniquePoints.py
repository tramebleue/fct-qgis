# -*- coding: utf-8 -*-

"""
UniquePoints - Generate a point if last vertex

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
from qgis.PyQt.QtCore import (
    QVariant
)

from qgis.core import (
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
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class UniquePoints(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Generate a point if last vertex
    """

    METADATA = AlgorithmMetadata.read(__file__, 'UniquePoints')


    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input layer'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Unique points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            layer.fields(),
            QgsWkbTypes.Point,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        points = set()
        vertices = 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
              break

            geometry = feature.geometry()
            if geometry.isMultipart():
                for polyline in geometry.asMultiPolyline():
                    points.add(polyline[0])
                    points.add(polyline[-1])
                    vertices = vertices + 2
            else:
                polyline = geometry.asPolyline()
                points.add(polyline[0])
                points.add(polyline[-1])
                vertices = vertices + 2         

            feedback.setProgress(int(current * total))

        total = 100.0 / len(points)
        
        feedback.pushConsoleInfo('Extracting %d points out of %d vertices' % (len(points), vertices))

        for current, p in enumerate(points):

            if feedback.isCanceled():
              break  

            feature = QgsFeature()
            
            feature.setGeometry(QgsGeometry.fromPointXY(p))

            sink.addFeature(feature)         

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
            
          



