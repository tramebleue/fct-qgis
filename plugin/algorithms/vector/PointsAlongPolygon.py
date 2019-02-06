# -*- coding: utf-8 -*-

"""
PointsAlongPolygon - Generate a point at the middle of each segment

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
    QgsGeometry,
    QgsFeature,
    QgsFeatureSink,
    QgsWkbTypes,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink
)

from ..metadata import AlgorithmMetadata


class PointsAlongPolygon(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Creates points at regular intervals along polygon geometries, including holes boundaries
    (contrary to qgis:createpointalonglines).
    Created points will have new attributes added for the distance along the geometry.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'PointsAlongPolygon')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    DISTANCE = 'DISTANCE'
    START_OFFSET = 'START_OFFSET'
    END_OFFSET = 'END_OFFSET'

    def initAlgorithm(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input layer'),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterDistance(
            self.DISTANCE,
            self.tr('Distance'),
            parentParameterName=self.INPUT,
            minValue=0.0,
            defaultValue=1.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)

        fields = source.fields()
        fields.append(QgsField('distance', QVariant.Double))
        fields.append(QgsField('angle', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields, QgsWkbTypes.Point,
            source.sourceCrs(),
            QgsFeatureSink.RegeneratePrimaryKey)

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        features = source.getFeatures()
        total = 100.0 / source.featureCount() if source.featureCount() else 0

        def points_along_polygon(input_feature, polygon):
            """ Iterates over rings,
                and generates points along each ring.
            """

            for i in range(polygon.childCount()):

                ring = polygon.childGeometry(i)
                length = ring.length()
                current_distance = 0.0

                while current_distance <= length:

                    point = ring.interpolatePoint(current_distance)
                    angle = math.degrees(input_geometry.interpolateAngle(current_distance))

                    output_feature = QgsFeature()
                    output_feature.setGeometry(QgsGeometry(point))
                    attrs = input_feature.attributes()
                    attrs.append(current_distance)
                    attrs.append(angle)
                    output_feature.setAttributes(attrs)
                    sink.addFeature(output_feature, QgsFeatureSink.FastInsert)

                    current_distance += distance

        for current, input_feature in enumerate(features):

            if feedback.isCanceled():
                break

            input_geometry = input_feature.geometry()

            if input_geometry:

                for part in input_geometry.constParts():
                    points_along_polygon(input_feature, part)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
