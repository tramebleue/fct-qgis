# -*- coding: utf-8 -*-

"""
DrapeVectors

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
    QgsFeature,
    QgsGeometry,
    QgsLineString,
    QgsMultiLineString,
    QgsMultiPolygon,
    QgsPoint,
    QgsPolygon,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from .utils import RasterDataAccess

class DrapeVectors(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Drape input vectors onto raster
        and interpolate additional vertices between original vertices
        to match pixels.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'DrapeVectors')

    INPUT = 'INPUT'
    RASTER = 'RASTER'
    BAND = 'BAND'
    OUTPUT = 'OUTPUT'

    def initParameters(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.RASTER,
            self.tr('Input Raster')))

        self.addParameter(QgsProcessingParameterBand(
            self.BAND,
            self.tr('Band'),
            parentLayerParameterName=self.RASTER,
            defaultValue=1))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        # return [QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Draped Features')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring

        if QgsWkbTypes.hasZ(inputWkbType):
            return inputWkbType

        return QgsWkbTypes.addZ(inputWkbType)

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring
        return super().supportInPlaceEdit(layer) \
            and QgsWkbTypes.hasZ(layer.wkbType()) \
            and QgsWkbTypes.isSingleType(layer.wkbType())

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        raster = self.parameterAsRasterLayer(parameters, self.RASTER, context)
        band = self.parameterAsInt(parameters, self.BAND, context)
        code1 = raster.crs().authid().split(':')[1]
        code2 = layer.sourceCrs().authid().split(':')[1]

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Multipart geometries are not currently supported'), True)
            return False

        self.data = RasterDataAccess(
            raster.dataProvider().dataSourceUri(),
            int(code1), int(code2),
            band=band)

        return True

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        with self.data:
            return super().processAlgorithm(parameters, context, feedback)


    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        def processLineString(line): # pylint: disable=unused-argument
            """ Drape simple linestring
            """

            points = [QgsPoint(x, y, z) for x, y, z, m in self.data.linestring(QgsGeometry(line))]
            return QgsLineString(points)

        def processPolygon(polygon):
            """ Drape simple polygon
            """

            rings = [
                processLineString(polygon.childGeometry(i))
                for i in range(polygon.childCount())
            ]

            new_polygon = QgsPolygon()
            ring = rings[0]
            new_polygon.setExteriorRing(ring)
            for ring in rings[1:]:
                new_polygon.addInteriorRing(ring)

            return new_polygon

        geometry = feature.geometry()

        if geometry.isMultipart():

            if QgsWkbTypes.singleType(geometry.wkbType()) == QgsWkbTypes.LineString:

                parts = QgsMultiLineString()

                for part in geometry.constParts():

                    # part instance of QgsLineString
                    linestring = processLineString(part)
                    parts.addGeometry(linestring)

            else:

                parts = QgsMultiPolygon()

                for part in geometry.constParts():

                    # part instance of QgsPolygon
                    polygon = processPolygon(part)
                    parts.addGeometry(polygon)

            outfeature = QgsFeature()
            outfeature.setAttributes(feature.attributes())
            outfeature.setGeometry(QgsGeometry(parts))


        else:

            if QgsWkbTypes.flatType(geometry.wkbType()) == QgsWkbTypes.LineString:

                linestring = processLineString(geometry)
                outfeature = QgsFeature()
                outfeature.setGeometry(QgsGeometry(linestring))
                outfeature.setAttributes(feature.attributes())

            else:

                polygon = [part for part in geometry.constParts()][0]
                new_polygon = processPolygon(polygon)
                outfeature.setGeometry(QgsGeometry(new_polygon))
                outfeature.setAttributes(feature.attributes())

        return [outfeature]
