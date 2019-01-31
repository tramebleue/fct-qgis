# -*- coding: utf-8 -*-

"""
Variable-length transects

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

import processing

from ..metadata import AlgorithmMetadata

class VariableLengthTransects(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Variable-length transects.
    Create transects of variable length specified in a field
    """

    METADATA = AlgorithmMetadata.read(__file__, 'VariableLengthTransects')

    LENGTH_FIELD = 'LENGTH_FIELD'
    INTERVAL = 'INTERVAL'

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterField(
            self.LENGTH_FIELD,
            self.tr('Length field'),
            parentLayerParameterName='INPUT',
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterNumber(
            self.INTERVAL,
            self.tr('Interval between transects'),
            defaultValue=20.0))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transects')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.LineString

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.length_field = self.parameterAsString(parameters, self.LENGTH_FIELD, context)
        self.interval = self.parameterAsDouble(parameters, self.INTERVAL, context)

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        transect_length = feature.attribute(self.length_field)
        geometry = feature.geometry()
        
        pt_dist = 0
        while pt_dist < geometry.length():
            origin_pt = geometry.interpolate(pt_dist)
            ptdist += self.interval

            



        return transects