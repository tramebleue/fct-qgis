# -*- coding: utf-8 -*-

"""
DrapeFeatures

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
    QgsPoint,
    QgsPolygon,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from .utils import RasterDataAccess

class DrapeFeatures(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Drape input features onto raster
        and interpolate additional vertices between original vertices
        to match pixels.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'DrapeFeatures')

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
        return [QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]

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

        self.data = RasterDataAccess(
            raster.dataProvider().dataSourceUri(),
            int(code1), int(code2),
            band=band)

        return True

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        with self.data:
            return super().processAlgorithm(parameters, context, feedback)


    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        geometry = feature.geometry()

        if geometry.isMultipart():

            raise QgsProcessingException(self.tr('Multipart geometries are not supported'))

        else:

            if QgsWkbTypes.flatType(geometry.wkbType()) == QgsWkbTypes.LineString:

                points = [QgsPoint(x, y, z) for x, y, z, m in self.data.linestring(geometry)]
                outfeature = QgsFeature()
                outfeature.setGeometry(QgsGeometry(QgsLineString(points)))
                outfeature.setAttributes(feature.attributes())

            else:

                polygon = [part for part in geometry.constParts()][0]
                rings = list()

                for i in range(polygon.ringCount()):
                    ring = polygon.childGeometry(i)
                    points = [QgsPoint(x, y, z) for x, y, z, m in self.data.linestring(QgsGeometry(ring))]
                    rings.append(QgsLineString(points))

                outfeature = QgsFeature()
                outfeature.setGeometry(QgsGeometry(QgsPolygon(rings)))
                outfeature.setAttributes(feature.attributes())

        return [outfeature]
