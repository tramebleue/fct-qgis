# -*- coding: utf-8 -*-

"""
Variable-Width Vertex-Wise Buffer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from math import degrees, atan2

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module,import-error
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

def segment_angle(a, b):
    """
    Parameters
    ----------

    a, b: QgsPointXY

    Returns
    -------

    Angle of segment [A, B] with x axis
    """

    # return degrees(QgsVector(b.x() - a.x(), b.y() - a.y()).angle(QgsVector(1, 0)))
    return degrees(atan2(b.y() - a.y(), b.x() - a.x()))

def minimum_oriented_box(geom):
    """
    Calculate QgsGeometry (Polygon) min. oriented box
    """

    exterior = geom.asPolygon()[0]
    p0 = QgsPointXY(exterior[0])
    min_box = geom.boundingBox()
    min_area = min_box.area()
    min_angle = 0.0
    min_height = min_box.height()
    min_width = min_box.width()
    min_box = QgsGeometry.fromRect(min_box)

    for i, p in enumerate(exterior[:-1]):

        angle = segment_angle(p, exterior[i+1])
        x = QgsGeometry(geom)
        x.rotate(angle, p0)
        box = x.boundingBox()
        area = box.area()

        if area < min_area:

            min_area = area
            min_angle = angle
            min_height = box.height()
            min_width = box.width()
            box = QgsGeometry.fromRect(box)
            box.rotate(-angle, p0)
            min_box = box

    return min_box, min_angle, min_height, min_width

class MinimumOrientedBoundingBox(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Calculate Polygon mininimum oriented box
    """

    METADATA = AlgorithmMetadata.read(__file__, 'MinimumOrientedBoundingBox')

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorPolygon]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Minimum Oriented Bounding Box')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.Polygon

    def outputFields(self, inputFields): #pylint: disable=no-self-use,unused-argument,missing-docstring

        fields = QgsFields(inputFields)
        appendUniqueField(QgsField('angle', QVariant.Double), fields)
        appendUniqueField(QgsField('height', QVariant.Double), fields)
        appendUniqueField(QgsField('width', QVariant.Double), fields)

        return fields

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, 'INPUT', context)

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Only simple polygons are supported.'), True)
            return False

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        geometry = feature.geometry()

        box, angle, height, width = minimum_oriented_box(geometry)
        new_feature = QgsFeature()
        new_feature.setAttributes(feature.attributes() + [
            angle,
            height,
            width
        ])
        new_feature.setGeometry(box)

        return [new_feature]
