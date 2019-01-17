# -*- coding: utf-8 -*-

"""
PropagateMeasure

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class PropagateMeasure(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Set M coordinate with respect to given `measure` field
    """

    METADATA = AlgorithmMetadata.read(__file__, 'PropagateMeasure')

    INPUT = 'INPUT'
    MEASURE_FIELD = 'GROUP_FIELD'
    MEASURE_DIRECTION = 'MEASURE_FIELD'

    DIRECTION_FORWARD = 0
    DIRECTION_REVERSE = 1

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterField(
            self.MEASURE_FIELD,
            self.tr('Measure Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterEnum(
            self.MEASURE_DIRECTION,
            self.tr('Measure Direction'),
            options=[self.tr(option) for option in ['Forward', 'Reverse']],
            defaultValue=1))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Measured Lines')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring

        if QgsWkbTypes.hasM(inputWkbType):
            return inputWkbType

        out = QgsWkbTypes.flatType(inputWkbType)
        if QgsWkbTypes.hasZ(inputWkbType):
            out = QgsWkbTypes.addZ(out)
        out = QgsWkbTypes.addM(out)

        return out

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring

        return super().supportInPlaceEdit(layer) \
            and QgsWkbTypes.hasM(layer.wkbType())

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.measure_field = self.parameterAsString(parameters, self.MEASURE_FIELD, context)
        self.direction = self.parameterAsInt(parameters, self.MEASURE_DIRECTION, context)
        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        measure = feature.attribute(self.measure_field)
        geometry = feature.geometry()

        if self.direction == self.DIRECTION_REVERSE:
            measure += geometry.length()
            sign = -1
        else:
            sign = 1

        if geometry.isMultipart():

            parts = QgsMultiLineString()

            for part in geometry.constParts():

                points = list()
                # previous = part.vertexAt(0)
                previous = None

                for vertex in part.vertices():

                    measure += sign*vertex.distance(previous) if previous else 0
                    point = QgsPoint(vertex.x(), vertex.y(), vertex.z(), measure)
                    points.append(point)
                    previous = vertex

                parts.addGeometry(QgsLineString(points))

            feature.setGeometry(QgsGeometry(parts))

        else:

            points = list()
            # previous = geometry.vertexAt(0)
            previous = None

            for vertex in geometry.vertices():

                measure += sign*vertex.distance(previous) if previous else 0
                point = QgsPoint(vertex.x(), vertex.y(), vertex.z(), measure)
                points.append(point)
                previous = vertex

            feature.setGeometry(QgsGeometry(QgsLineString(points)))

        return [feature]
