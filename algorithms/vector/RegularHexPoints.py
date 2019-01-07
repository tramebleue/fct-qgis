# -*- coding: utf-8 -*-

"""
RegularHexPoints - Generate a regular hexagon grid of points

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from math import sqrt, floor

from qgis.PyQt.QtCore import (
    QVariant
)

from qgis.core import (
    QgsGeometry,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPointXY,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

def asQgsFields(*fields):

    out = QgsFields()
    for field in fields:
        out.append(field)
    return out

def resolveField(source, field):

    idx = source.fields().lookupField(field)
    return source.fields().at(idx) if idx > -1 else None

class RegularHexPoints(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Generate a regular hexagon grid of points,
        such as all the points are within the same distance.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'RegularHexPoints')

    INPUT = 'INPUT'
    PK_FIELD = 'PK_FIELD'
    DISTANCE = 'DISTANCE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration):

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input Polygons'),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Primary Key Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterDistance(
            self.DISTANCE,
            self.tr('Distance'),
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Regular Hex Points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback):

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)

        h = 0.5*sqrt(3)*distance

        fields = asQgsFields(
            QgsField('PID', QVariant.Int, len=10),
            QgsField('X', QVariant.Double, len=10, prec=2),
            QgsField('Y', QVariant.Double, len=10, prec=2),
            resolveField(layer, pk_field)
        )

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            QgsWkbTypes.Point,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        fid = 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            extent = feature.geometry().boundingBox()
            xmin = extent.xMinimum()
            ymin = extent.yMinimum()
            xmax = extent.xMaximum()
            ymax = extent.yMaximum()
            pk = feature.attribute(pk_field)

            baseline = True

            x0 = floor(xmin / distance) * distance
            y0 = floor(ymin / h) * h

            if y0 - h > ymin:

                y0 = y0 - h
                baseline = False

            if x0 - 0.5 * distance > xmin:
                x1 = x0 - 0.5 * distance
            else:
                x1 = x0 + 0.5 * distance

            y = y0

            while y < ymax:

                if baseline:
                    x = x0
                else:
                    x = x1

                while x < xmax:

                    geom = QgsGeometry.fromPointXY(QgsPointXY(x, y))

                    if feature.geometry().contains(geom):

                        fid = fid + 1
                        out_feature = QgsFeature()
                        out_feature.setAttributes([
                                fid,
                                x,
                                y,
                                pk
                            ])
                        out_feature.setGeometry(geom)
                        sink.addFeature(out_feature)

                    x = x + distance

                y = y + h
                baseline = not baseline

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
