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

import math

from qgis.core import ( #pylint: disable=import-error,no-name-in-module
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameters,
    QgsPropertyDefinition,
    QgsVector,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def transect(origin, direction, length):
    """
    Parameters
    ----------

    origin: QgsPointXY
        origin of transect

    direction: QgsVector
         direction of transect

    length: float, distance
        total length of transect to be generated
    """

    t1 = QgsPointXY(origin.x() - 0.5*length*direction.x(), origin.y() - 0.5*length*direction.y())
    t2 = QgsPointXY(origin.x() + 0.5*length*direction.x(), origin.y() + 0.5*length*direction.y())

    return QgsGeometry.fromPolylineXY([t1, t2])

class VariableLengthTransects(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Variable-length transects.

    Create transects of variable length specified in a field,
    spaced by given interval along the generating polyline.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'VariableLengthTransects')

    LENGTH = 'LENGTH'
    INTERVAL = 'INTERVAL'

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        param_length = QgsProcessingParameterDistance(
            self.LENGTH,
            self.tr('Length of Transect'),
            parentParameterName='INPUT',
            defaultValue=10.0)
        param_length.setIsDynamic(True)
        param_length.setDynamicLayerParameterName(self.LENGTH)
        param_length.setDynamicPropertyDefinition(
            QgsPropertyDefinition(
                self.LENGTH,
                self.tr('Length of Transect'),
                QgsPropertyDefinition.Double))
        self.addParameter(param_length)

        param_distance = QgsProcessingParameterDistance(
            self.INTERVAL,
            self.tr('Distance Between Transects'),
            parentParameterName='INPUT',
            defaultValue=20.0)
        param_distance.setIsDynamic(True)
        param_distance.setDynamicLayerParameterName(self.INTERVAL)
        param_distance.setDynamicPropertyDefinition(
            QgsPropertyDefinition(
                self.INTERVAL,
                self.tr('Distance Between Transects'),
                QgsPropertyDefinition.Double))
        self.addParameter(param_distance)

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transects')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.LineString

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.dynamic_parameters = dict()

        self.setDynamicParameterAsDouble(parameters, self.LENGTH, context)
        self.setDynamicParameterAsDouble(parameters, self.INTERVAL, context)

        return True

    def setDynamicParameterAsDouble(self, parameters, name, context):
        """
        Register a dynamic parameter of type double with name `name`
        """

        param_default = self.parameterAsDouble(parameters, name, context)
        dynamic = QgsProcessingParameters.isDynamic(parameters, name)
        param_property = parameters[name] if dynamic else None
        self.dynamic_parameters[name] = (param_property, param_default)

    def dynamicParameterAsDouble(self, name, context):
        """
        Return the contextual value of parameter `name`, as a double.
        """

        if name in self.dynamic_parameters:

            param_property, param_default = self.dynamic_parameters[name]

            if param_property:
                value, ok = param_property.valueAsDouble(context.expressionContext(), param_default)
                return value if ok else param_default
            else:
                return param_default

        else:

            raise QgsProcessingException('Unknown parameter %s' % name)

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        cursor = 0.0
        length = self.dynamicParameterAsDouble(self.LENGTH, context)
        interval = self.dynamicParameterAsDouble(self.INTERVAL, context)
        geometry = feature.geometry()
        transects = list()

        while cursor < geometry.length():

            origin = geometry.interpolate(cursor).asPoint()
            angle = geometry.interpolateAngle(cursor)
            direction = QgsVector(-math.cos(angle), math.sin(angle))

            new_feature = QgsFeature()
            new_feature.setAttributes(feature.attributes())
            new_feature.setGeometry(transect(origin, direction, length))
            transects.append(new_feature)

            cursor += interval

        return transects

