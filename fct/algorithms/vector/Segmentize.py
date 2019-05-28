# -*- coding: utf-8 -*-

"""
Segmentize

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import ( #pylint: disable=import-error
    QVariant
)

from qgis.core import ( #pylint: disable=import-error
    QgsGeometry,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsLineString,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

class Segmentize(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Break a linestring into segments of equal length
    """

    METADATA = AlgorithmMetadata.read(__file__, 'Segmentize')

    INPUT = 'INPUT'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input linestrings'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterDistance(
            self.DISTANCE,
            self.tr('Distance'),
            parentParameterName=self.INPUT,
            defaultValue=20.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Segmentized'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('DGO', QVariant.Int), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        def emit(feature, segment, fid):
            """
            Output current segment
            """
            outfeature = QgsFeature()
            outfeature.setGeometry(QgsGeometry(QgsLineString(segment).clone()))
            outfeature.setAttributes(feature.attributes() + [fid])
            sink.addFeature(outfeature)

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            geom = feature.geometry()
            length = geom.length()
            num_segments = length // distance
            dgo = 1

            if num_segments <= 1:

                # no need to split,
                # just output as it is

                outfeature = QgsFeature()
                outfeature.setGeometry(geom)
                outfeature.setAttributes(feature.attributes() + [dgo])
                sink.addFeature(outfeature)

            else:

                # we distribute the round-off on both ends
                extra_length = length % distance * 0.5

                for i, point in enumerate(geom.vertices()):

                    if i == 0:
                        previous = point
                        measure = 0.0
                        split_at = distance + extra_length
                        segment = [point]
                        continue

                    measure += point.distance(previous)

                    if measure > split_at:

                        while measure > split_at:

                            split_point = geom.interpolate(split_at).vertexAt(0)
                            segment.append(split_point)
                            emit(feature, segment, dgo)
                            dgo += 1

                            segment = [split_point]
                            split_at += distance

                            if length - split_at < distance:
                                split_at = float('inf')

                        segment.append(point)

                    elif measure == split_at:

                        segment.append(point)
                        emit(feature, segment, dgo)
                        dgo += 1

                        segment = [point]
                        split_at += distance

                        if length - split_at < distance:
                            split_at = float('inf')

                    else:

                        segment.append(point)

                    previous = point

                emit(feature, segment, dgo)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
