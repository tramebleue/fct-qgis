# -*- coding: utf-8 -*-

"""
Knick Points Detection

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

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameters,
    QgsPropertyDefinition,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def transect(segment, length):
    """
    Parameters
    ----------

    segment: QgsGeometry, (2-points) Polyline
    length: float, distance
        total length of transect to be generated
    """

    start_point = segment.interpolate(0.0).asPoint()
    end_point = segment.interpolate(segment.length()).asPoint()
    mid_point = segment.interpolate(0.5 * segment.length()).asPoint()

    a = end_point.x() - start_point.x()
    b = end_point.y() - start_point.y()
    d = math.sqrt(a**2 + b**2)
    normal = QgsPointXY(-b / d, a / d)
    t1 = QgsPointXY(mid_point.x() - 0.5*length*normal.x(), mid_point.y() - 0.5*length*normal.y())
    t2 = QgsPointXY(mid_point.x() + 0.5*length*normal.x(), mid_point.y() + 0.5*length*normal.y())

    return QgsGeometry.fromPolylineXY([t1, t2])

class OrthogonalTransects(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Creates line transects orthogonal to each input segment,
    passing through the midpoint of the generating segment.

    See also:

    - native:transect
    """

    METADATA = AlgorithmMetadata.read(__file__, 'OrthogonalTransects')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    LENGTH = 'LENGTH'

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        # self.addParameter(QgsProcessingParameterFeatureSource(
        #     self.INPUT,
        #     self.tr('Stream Network Aggregated by Hack Order with Z Coordinate'),
        #     [QgsProcessing.TypeVectorLine]))

        param_length = QgsProcessingParameterNumber(
            self.LENGTH,
            self.tr('Transect Length'),
            defaultValue=200.0)
        param_length.setIsDynamic(True)
        param_length.setDynamicLayerParameterName('INPUT')
        param_length.setDynamicPropertyDefinition(
            QgsPropertyDefinition(
                self.LENGTH,
                self.tr('Transect Length'),
                QgsPropertyDefinition.DoublePositive))
        self.addParameter(param_length)

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Transects'),
        #     QgsProcessing.TypeVectorLine))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transects')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.LineString

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.length = self.parameterAsDouble(parameters, self.LENGTH, context)
        dynamic = QgsProcessingParameters.isDynamic(parameters, self.LENGTH)
        self.length_property = parameters[self.LENGTH] if dynamic else None

        return True

    def transect_length(self, context):
        """ Return feature-specific length or fixed length parameter """

        if self.length_property:

            value, ok = self.length_property.valueAsDouble(context.expressionContext(), self.length)
            return value if ok else self.length

        else:

            return self.length


    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        out_feature = QgsFeature()
        geom = feature.geometry()

        if geom.length() > 0:

            transect_geom = transect(geom, self.transect_length(context))
            out_feature.setGeometry(transect_geom)
            out_feature.setAttributes(feature.attributes())

        return [out_feature]
