# -*- coding: utf-8 -*-

"""
Variable-Width Vertex-Wise Buffer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class LineStringBufferByM(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Variable-Width Vertex-Wise Buffer.
    Local buffer width at each vertex is determined from M coordinate.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LineStringBufferByM')

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Buffer')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.Polygon

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, 'INPUT', context)

        if not QgsWkbTypes.hasM(layer.wkbType()):
            feedback.reportError(self.tr('Input must have M coordinate.'), True)
            return False

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        features = []

        for geometry in feature.geometry().asGeometryCollection():

            new_geometry = geometry.variableWidthBufferByM(5)
            new_feature = QgsFeature()
            new_feature.setAttributes(feature.attributes())
            new_feature.setGeometry(new_geometry)
            features.append(new_feature)

        return features
