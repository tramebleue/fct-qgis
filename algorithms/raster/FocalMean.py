# -*- coding: utf-8 -*-

"""
FocalMean - Computes mean value of raster data in a fixed window
            around each input point.

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
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterString
)

from ..metadata import AlgorithmMetadata

from .utils import RasterDataAccess

class FocalMean(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Computes mean value of raster data in a fixed window
        around each input point.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FocalMean')

    INPUT = 'INPUT'
    POINTS = 'POINTS'
    WIDTH = 'WIDTH'
    HEIGHT = 'HEIGHT'
    FIELD = 'FIELD'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Input Raster')))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS,
            self.tr('Data Points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterString(
            self.FIELD,
            self.tr('Output Field'),
            defaultValue='VALUE'))

        self.addParameter(QgsProcessingParameterDistance(
            self.WIDTH,
            self.tr('Window Width (map units)')))

        self.addParameter(QgsProcessingParameterDistance(
            self.HEIGHT,
            self.tr('Window Height (map units)')))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Focal Mean'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        points = self.parameterAsSource(parameters, self.POINTS, context)
        width = self.parameterAsDouble(parameters, self.WIDTH, context)
        height = self.parameterAsDouble(parameters, self.HEIGHT, context)
        output_field = self.parameterAsString(parameters, self.FIELD, context)

        code1 = raster.crs().authid().split(':')[1]
        code2 = points.sourceCrs().authid().split(':')[1]

        fields = QgsFields(points.fields())
        fields.append(QgsField(output_field, QVariant.Double, len=21, prec=6))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            points.wkbType(),
            points.sourceCrs())

        total = 100.0 / points.featureCount() if points.featureCount() else 0
        uri = raster.dataProvider().dataSourceUri()

        with RasterDataAccess(uri, int(code1), int(code2)) as rdata:

            for current, feature in enumerate(points.getFeatures()):

                if feedback.isCanceled():
                    break

                data = rdata.window(feature.geometry().asPoint(), width, height)
                if data is not None:
                    data[data == rdata.nodata] = np.nan
                    value = np.nanmean(data)
                else:
                    value = None

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [float(value)])
                sink.addFeature(outfeature)

                feedback.setProgress(int(current * total))


        return {self.OUTPUT: dest_id}
