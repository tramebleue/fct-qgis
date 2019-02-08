# -*- coding: utf-8 -*-

"""
Locate Point Along Line

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
    QgsGeometry,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

class LocatePointAlongLine(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Find the nearest point on the nearest line,
    and transfer M and Z coordinates.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LocatePointAlongLine')

    INPUT = 'INPUT'
    LINES = 'LINES'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'
    NO_DATA = 'NO_DATA'
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

        self.addParameter(QgsProcessingParameterNumber(
            self.NO_DATA,
            self.tr('M|Z No-Data Value For Unmatched Points'),
            defaultValue=-999))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Referenced Points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        lines = self.parameterAsSource(parameters, self.LINES, context)
        search_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)
        nodata = self.parameterAsDouble(parameters, self.NO_DATA, context)

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

        wkbType = QgsWkbTypes.PointM
        withz = QgsWkbTypes.hasZ(lines.wkbType())
        withm = QgsWkbTypes.hasM(lines.wkbType())

        if withz:
            wkbType = QgsWkbTypes.addZ(wkbType)

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

                pt = point.asPoint()
                outfeature = QgsFeature()
                outfeature.setGeometry(QgsGeometry(
                    QgsPoint(
                        pt.x(),
                        pt.y(),
                        nearest_point.z() if withz else None,
                        nearest_point.m() if withm else measure
                    )))
                outfeature.setAttributes(
                    feature.attributes() + \
                    nearest_line.attributes() + [
                        min_distance
                    ])
                sink.addFeature(outfeature)

            else:

                pt = point.asPoint()
                feature.setGeometry(QgsGeometry(
                    QgsPoint(
                        pt.x(),
                        pt.y(),
                        nodata if withz else None,
                        nodata
                    )))
                sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
