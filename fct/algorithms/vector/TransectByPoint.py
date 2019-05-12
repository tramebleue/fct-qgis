# -*- coding: utf-8 -*-

"""
Transect By Point

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
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameters,
    QgsPropertyDefinition,
    QgsSpatialIndex,
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

class TransectByPoint(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Creates transects along line at specified points.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'TransectByPoint')

    LINES = 'LINES'
    LENGTH = 'LENGTH'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LINES,
            self.tr('Lines'),
            [QgsProcessing.TypeVectorLine]))

        param_length = QgsProcessingParameterDistance(
            self.LENGTH,
            self.tr('Length of Transect'),
            parentParameterName='INPUT',
            defaultValue=10.0)
        param_length.setIsDynamic(True)
        param_length.setDynamicLayerParameterName('INPUT')
        param_length.setDynamicPropertyDefinition(
            QgsPropertyDefinition(
                self.LENGTH,
                self.tr('Length of Transect'),
                QgsPropertyDefinition.Double))
        self.addParameter(param_length)

        self.addParameter(QgsProcessingParameterDistance(
            self.SEARCH_DISTANCE,
            self.tr('Search Distance'),
            parentParameterName='INPUT',
            defaultValue=50.0))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorPoint]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transects')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.LineString

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.dynamic_parameters = dict()
        self.registerDynamicParameterAsDouble(parameters, self.LENGTH, context)

        self.lines = self.parameterAsSource(parameters, self.LINES, context)
        self.search_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)
        self.line_index = QgsSpatialIndex(self.lines.getFeatures())

        return True

    def registerDynamicParameterAsDouble(self, parameters, name, context):
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

            return param_default

        else:

            raise QgsProcessingException('Unknown parameter %s' % name)

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        transects = []
        length = self.dynamicParameterAsDouble(self.LENGTH, context)
        point = feature.geometry()

        nearest_line = None
        min_distance = float('inf')

        rect = point.boundingBox()
        rect.grow(self.search_distance)
        candidates = self.line_index.intersects(rect)
        request = QgsFeatureRequest().setFilterFids(candidates)

        for line in self.lines.getFeatures(request):

            distance = line.geometry().distance(point)

            if distance < self.search_distance and distance < min_distance:

                min_distance = distance
                nearest_line = line

        if nearest_line:

            geometry = nearest_line.geometry()
            cursor = geometry.lineLocatePoint(point)
            # origin = geometry.interpolate(cursor)
            angle = geometry.interpolateAngle(cursor)
            direction = QgsVector(-math.cos(angle), math.sin(angle))

            new_feature = QgsFeature()
            new_feature.setAttributes(feature.attributes())
            # new_feature.setGeometry(transect(origin.asPoint(), direction, length))
            new_feature.setGeometry(transect(point.asPoint(), direction, length))
            transects.append(new_feature)

        return transects
