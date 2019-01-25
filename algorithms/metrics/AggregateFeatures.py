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

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes,
    NULL
)

from ..metadata import AlgorithmMetadata
from ...utils.hubert_kehagias_dp import HubertKehagiasSegmentation

class AggregateFeatures(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Aggregate disaggregated objects with respect to a given metric,
    using the Hubert-Kehagias segmentation procedure.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'AggregateFeatures')

    INPUT = 'INPUT'
    ORDERING_FIELD = 'ORDERING_FIELD'
    METRIC_FIELD = 'METRIC_FIELD'
    DISSOLVE = 'DISSOLVE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input features to aggregate'),
            [QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterField(
            self.METRIC_FIELD,
            self.tr('Segmentation Metric'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterField(
            self.ORDERING_FIELD,
            self.tr('Ordering Property'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any))

        self.addParameter(QgsProcessingParameterBoolean(
            self.DISSOLVE,
            self.tr('Dissolve Objects'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Aggregated Geographic Objects'),
            QgsProcessing.TypeVectorAnyGeometry))


    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        metric_field = self.parameterAsString(parameters, self.METRIC_FIELD, context)
        ordering_field = self.parameterAsString(parameters, self.ORDERING_FIELD, context)
        dissolve = self.parameterAsBool(parameters, self.DISSOLVE, context)

        feedback.pushInfo('Create metric sequence...')
        sequence = []

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):
            if feedback.isCanceled():
                break

            distance = feature.attribute(ordering_field)
            value = feature.attribute(metric_field)

            if value != NULL:
                sequence.append([distance, value, feature.id()])

            feedback.setProgress(int(current*total))

        sequence = sorted(sequence)

        feedback.pushInfo('Perform Hubert-Kehagias Segmentation ...')

        serie = np.array([float(item[1]) for item in sequence])
        segmentation = HubertKehagiasSegmentation(serie)
        kopt = segmentation.kopt(len(sequence) // 3)

        feedback.pushInfo('Output aggregated features')

        if dissolve:

            layer_fields = layer.fields()
            metric_field_idx = layer_fields.lookupField(metric_field)
            mean_field = layer_fields.at(metric_field_idx)
            std_field = QgsField(mean_field)
            std_field.setName('STD')

            fields = QgsFields()
            fields.append(QgsField('ID_AGO', QVariant.Int, len=10, prec=0))
            fields.append(mean_field)
            fields.append(std_field)

            (sink, dest_id) = self.parameterAsSink(
                parameters, self.OUTPUT, context,
                fields,
                # QgsWkbTypes.MultiPolygon,
                layer.wkbType(),
                layer.sourceCrs())

            def output_feature(geometry, seg_idx, mean, std):
                """ Emit output feature """

                outfeature = QgsFeature()
                outfeature.setGeometry(geometry)
                outfeature.setAttributes([
                    seg_idx,
                    float(mean),
                    float(std)
                ])

                sink.addFeature(outfeature)

            srclayer = context.getMapLayer(layer.sourceName())

            breakpoints = segmentation.breakpoints(kopt)
            current = 0

            for seg_idx, (start, stop) in enumerate(zip(breakpoints[:-1], breakpoints[1:])):

                geometries = list()
                request = QgsFeatureRequest()
                request.setFilterFids([item[2] for item in sequence[start:stop]])
                for feature in srclayer.getFeatures(request):
                    geometries.append(feature.geometry())
                    current += 1

                geometry = QgsGeometry.unaryUnion(geometries)
                mean = serie[start:stop].mean()
                std = serie[start:stop].std()

                if QgsWkbTypes.flatType(geometry.wkbType()) == QgsWkbTypes.MultiLineString:

                    for linestring in geometry.mergeLines().asGeometryCollection():
                        output_feature(linestring, seg_idx, mean, std)

                elif QgsWkbTypes.flatType(geometry.wkbType()) == QgsWkbTypes.MultiPolygon:

                    for polygon in geometry.asGeometryCollection():
                        output_feature(polygon, seg_idx, mean, std)

                else:

                    output_feature(geometry, seg_idx, mean, std)

                feedback.setProgress(int(current*total))

        else:

            fields = QgsFields(layer.fields())
            fields.append(QgsField('ID_AGO', QVariant.Int, len=10, prec=0))

            (sink, dest_id) = self.parameterAsSink(
                parameters, self.OUTPUT, context,
                fields,
                layer.wkbType(), # QgsWkbTypes.MultiPolygon,
                layer.sourceCrs())

            segments = segmentation.segments(kopt)
            feature_segments = {sequence[i][2]: int(segment) for i, segment in enumerate(segments)}

            for current, feature in enumerate(layer.getFeatures()):

                if feedback.isCanceled():
                    break

                outfeature = QgsFeature()
                outfeature.setGeometry(QgsGeometry(feature.geometry()))
                outfeature.setAttributes(feature.attributes() + [
                    feature_segments.get(feature.id(), None)
                ])

                sink.addFeature(outfeature)

                feedback.setProgress(int(current*total))

        return {
            self.OUTPUT: dest_id
        }
