# -*- coding: utf-8 -*-

"""
Features aggregation by Hubert test

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import numpy as np 
import processing

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterBoolean,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ...utils.hubert_kehagias_dp import HubertKehagiasSegmentation

class HubertTest(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Features (polygons, polylines or points) aggregation by Hubert test on 
        a metric

        References:


    """

    METADATA = AlgorithmMetadata.read(__file__, 'HubertTest')

    INPUT_FEATURES = 'INPUT_FEATURES'
    DISTANCE_FIELD = 'DISTANCE_FIELD'
    METRIC_FIELD = 'METRIC_FIELD'
    OUTPUT_FEATURES = 'OUTPUT_FEATURES'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT_FEATURES,
            self.tr('Input features to aggregate'),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterField(
            self.METRIC_FIELD,
            self.tr('Field containing metric for Hubert Test'),
            parentLayerParameterName=self.INPUT_FEATURES,
            type=QgsProcessingParameterField.Any))

        self.addParameter(QgsProcessingParameterField(
            self.DISTANCE_FIELD,
            self.tr('Field containing distance to sort features'),
            parentLayerParameterName=self.INPUT_FEATURES,
            type=QgsProcessingParameterField.Any))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT_FEATURES,
            self.tr('Output aggregated features'),
            QgsProcessing.TypeVectorPolygon))


    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring
        
        layer = self.parameterAsSource(parameters, self.INPUT_FEATURES, context)
        metric_field = self.parameterAsString(parameters, self.METRIC_FIELD, context)
        distance_field = self.parameterAsString(parameters, self.DISTANCE_FIELD, context)

        fields = QgsFields(layer.fields())
        fields.append(QgsField('ID_AGO', QVariant.Int, len=10, prec=0))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT_FEATURES, context,
            fields,
            QgsWkbTypes.MultiPolygon,
            layer.sourceCrs())

        feedback.pushInfo('Delete NULL features...')
        SelectDGOs = processing.run('native:extractbyexpression',
                            {
                              'EXPRESSION': "{} IS NOT NULL".format(metric_field),
                              'INPUT': self.parameterAsVectorLayer(parameters, self.INPUT_FEATURES, context),
                              'OUTPUT': 'memory:'
                            }, context=context)


        feedback.pushInfo('Create metric sequence...')
        sequence = []
        for current, feature in enumerate(SelectDGOs['OUTPUT'].getFeatures()):
            if feedback.isCanceled():
                break

            distance = feature.attribute(distance_field)
            value = feature.attribute(metric_field)

            sequence.append([distance, value, feature.id()])

        sequence = np.array(sequence)
        sequence = sequence[sequence[:,0].argsort()]
        sorted_values = sequence[:,1]

        feedback.pushInfo('Segment sequence by Hubert Test...')
        segmentation = HubertKehagiasSegmentation(sorted_values)
        kopt = segmentation.kopt(len(sequence) // 3)

        breakpoints = segmentation.segments(kopt)
        segments = np.zeros(len(sequence), dtype=np.uint16)
        for segment, (start,stop) in enumerate(zip(breakpoints[:-1], breakpoints[1:])):
            segments[start:stop] = segment

        feature_segments = {sequence[i][2]: segment for i, segment in enumerate(segments)}

        for current, feature in enumerate(SelectDGOs['OUTPUT'].getFeatures()):
            if feedback.isCanceled():
                break
            
            object = QgsFeature()
            object.setGeometry(QgsGeometry(feature.geometry()))
            object.setAttributes(feature.attributes() + [
                int(feature_segments[feature.id()])
            ])

            sink.addFeature(object)

        return {
            self.OUTPUT_FEATURES: dest_id
            }
