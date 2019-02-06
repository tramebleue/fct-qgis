# -*- coding: utf-8 -*-

"""
Distance To Other Layer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class DistanceToOtherLayer(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute distance from features in layer A
    to the nearest feature in layer B,
    given a maximum search distance.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'DistanceToOtherLayer')

    INPUT = 'INPUT'
    TO_LAYER = 'TO_LAYER'
    TO_LAYER_PK_FIELD = 'TO_LAYER_PK_FIELD'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input layer'),
            [QgsProcessing.TypeVectorAnyGeometry]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.TO_LAYER,
            self.tr('Other Layer'),
            [QgsProcessing.TypeVectorAnyGeometry]))

        self.addParameter(QgsProcessingParameterField(
            self.TO_LAYER_PK_FIELD,
            self.tr('Other Layer Primary Key'),
            parentLayerParameterName=self.TO_LAYER,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterDistance(
            self.SEARCH_DISTANCE,
            self.tr('Search Distance'),
            parentParameterName=self.INPUT,
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Distance'),
            QgsProcessing.TypeVectorAnyGeometry))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        to_layer = self.parameterAsSource(parameters, self.TO_LAYER, context)
        to_layer_pk_field = self.parameterAsString(parameters, self.TO_LAYER_PK_FIELD, context)
        search_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)

        spatial_index = QgsSpatialIndex(to_layer.getFeatures())

        pk_field_idx = to_layer.fields().lookupField(to_layer_pk_field)
        pk_field_instance = to_layer.fields().at(pk_field_idx)

        fields = QgsFields(layer.fields())
        fields.append(pk_field_instance)
        fields.append(QgsField('DISTANCE', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        is_point_layer = QgsWkbTypes.flatType(to_layer.wkbType()) == QgsWkbTypes.Point
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            if is_point_layer:

                point = feature.geometry().centroid().asPoint()
                request = QgsFeatureRequest().setFilterFids(spatial_index.nearestNeighbor(point, 1))

            else:

                search_box = feature.geometry().boundingBox()
                search_box.grow(search_distance)
                request = QgsFeatureRequest().setFilterFids(spatial_index.intersects(search_box))

            min_distance = float('inf')
            match_pk = None

            for other_feature in to_layer.getFeatures(request):

                distance = feature.geometry().distance(other_feature.geometry())

                if distance < min_distance:
                    min_distance = distance
                    match_pk = other_feature.attribute(to_layer_pk_field)

            new_feature = QgsFeature()
            new_feature.setGeometry(feature.geometry())

            if match_pk is None:

                new_feature.setAttributes(
                    feature.attributes() + [
                        None,
                        None
                    ])

            else:

                new_feature.setAttributes(
                    feature.attributes() + [
                        match_pk,
                        min_distance
                    ])

            sink.addFeature(new_feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
