# -*- coding: utf-8 -*-

"""
Extract Coordinates (X, Y, Z, M) As Fields

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
    QgsCoordinateReferenceSystem,
    QgsExpression,
    QgsLineString,
    QgsGeometry,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPoint,
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

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

class ExtractCoordinatesAsFields(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Extract coordinates (X, Y, Z, M) as new numeric fields.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ExtractCoordinatesAsFields')

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorPoint]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Extracted Coordinates')

    def outputFields(self, inputFields): #pylint: disable=no-self-use,missing-docstring
        appendUniqueField(QgsField('X', QVariant.Double), inputFields)
        appendUniqueField(QgsField('Y', QVariant.Double), inputFields)
        appendUniqueField(QgsField('Z', QVariant.Double), inputFields)
        appendUniqueField(QgsField('M', QVariant.Double), inputFields)
        return inputFields

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        geometry = feature.geometry()
        point = geometry.vertexAt(0)

        new_feature = QgsFeature()
        new_feature.setGeometry(geometry)
        new_feature.setAttributes(feature.attributes() + [
            point.x(),
            point.y(),
            point.z(),
            point.m()
        ])

        return [new_feature]