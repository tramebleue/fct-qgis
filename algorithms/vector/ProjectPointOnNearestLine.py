# -*- coding: utf-8 -*-

"""
ProjectPointsAlongLine

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import ( #pylint: disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( #pylint: disable=import-error,no-name-in-module
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def createUniqueFieldName(name, fields):
    """
    Return a new name that is unique within `fields`
    """

    if fields.lookupField(name) == -1:
        return name

    if len(name) > 8:
        basename = name[:8]
    else:
        basename = name

    i = 0
    unique_name = basename + '_%d' % i

    while fields.lookupField(unique_name) > -1:
        i += 1
        unique_name = basename + '_%d' % i

    return unique_name

def appendUniqueField(field, fields):
    """
    Create a unique name for `field` within `fields`,
    and append `field` to `fields`.
    """

    if fields.lookupField(field.name()) > -1:
        field.setName(createUniqueFieldName(field.name(), fields))
    fields.append(field)

class ProjectPointOnNearestLine(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Project points to the nearest line,
    ie. find the nearest point on the nearest line.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ProjectPointOnNearestLine')

    INPUT = 'INPUT'
    LINES = 'LINES'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    INCLUDE_NOT_MATCHING = 'INCLUDE_NOT_MATCHING'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.LINES,
            self.tr('Lines'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterDistance(
            self.SEARCH_DISTANCE,
            self.tr('Search Distance'),
            parentParameterName=self.INPUT,
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterBoolean(
            self.INCLUDE_NOT_MATCHING,
            self.tr('Include Points Matching No Lines'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Projected Points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        lines = self.parameterAsSource(parameters, self.LINES, context)
        search_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)
        include_all = self.parameterAsBool(parameters, self.INCLUDE_NOT_MATCHING, context)

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Multipart points are not currently supported'), True)
            return {}

        if QgsWkbTypes.isMultiType(lines.wkbType()):
            feedback.reportError(self.tr('Multipart lines are not currently supported'), True)
            return {}

        fields = QgsFields(layer.fields())

        for field in lines.fields():
            appendUniqueField(field, fields)

        appendUniqueField(QgsField('DISTANCE', QVariant.Double), fields)

        wkbType = QgsWkbTypes.Point

        if QgsWkbTypes.hasZ(lines.wkbType()):
            wkbType = QgsWkbTypes.addZ(wkbType)
        
        if QgsWkbTypes.hasM(lines.wkbType()):
            wkbType = QgsWkbTypes.addM(wkbType)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            wkbType,
            layer.sourceCrs())

        line_index = QgsSpatialIndex(lines.getFeatures())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            point = feature.geometry()
            nearest_line = None
            min_distance = float('inf')

            rect = point.boundingBox()
            rect.grow(search_distance)

            candidates = line_index.intersects(rect)
            request = QgsFeatureRequest().setFilterFids(candidates)

            for line in lines.getFeatures(request):

                distance = line.geometry().distance(point)

                if distance < search_distance and distance < min_distance:

                    min_distance = distance
                    nearest_line = line

            if nearest_line:

                measure = nearest_line.geometry().lineLocatePoint(point)
                nearest_point = nearest_line.geometry().interpolate(measure)

                outfeature = QgsFeature()
                outfeature.setGeometry(nearest_point)
                outfeature.setAttributes(
                    feature.attributes() + \
                    nearest_line.attributes() + [
                        min_distance
                    ])
                sink.addFeature(outfeature)

            elif include_all:

                sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
