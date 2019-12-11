# -*- coding: utf-8 -*-

"""
Upstream Downstream Link

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
from osgeo import gdal
# import osr

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module,import-error
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterRasterLayer
)

from ..util import appendUniqueField
from ..metadata import AlgorithmMetadata

def worldtopixel(sequence, transform):
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (px, py)
    """
    return np.int32(np.round((sequence - [transform[0], transform[3]]) / [transform[1], transform[5]] - 0.5))

class UpstreamDownstreamLink(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    For each input point,
    find a matching downstream point,
    following the provided D8 flow direction raster.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'UpstreamDownstreamLink')

    FLOW = 'FLOW'
    INPUT = 'INPUT'
    PK_FIELD = 'PK_FIELD'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input Points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Primary Key'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction (D8)')))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Linked Points'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        flow_ds = gdal.OpenEx(flow_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        transform = flow_ds.GetGeoTransform()
        width = flow_ds.RasterXSize
        height = flow_ds.RasterYSize
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        nodata = -1
        noflow = 0

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('DOWNID', QVariant.Int), fields)
        appendUniqueField(QgsField('DOWNX', QVariant.Double), fields)
        appendUniqueField(QgsField('DOWNY', QVariant.Double), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate
            """

            return px >= 0 and py >= 0 and px < width and py < height

        fids = list()
        coords = list()

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        feedback.setProgressText(self.tr("Build point index ..."))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            point = feature.geometry().asPoint()
            x = point.x()
            y = point.y()

            fids.append(feature.attribute(pk_field))
            coords.append((x, y))

        pixels = {(px, py): k for k, (px, py) in enumerate(worldtopixel(np.array(coords), transform))}

        feedback.setProgressText(self.tr("Search for downstream points ..."))

        ci = [-1, -1,  0,  1,  1,  1,  0, -1]
        cj = [ 0,  1,  1,  1,  0, -1, -1, -1]

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            point = feature.geometry().asPoint()
            px, py = worldtopixel(np.array((point.x(), point.y())), transform)
            
            ide = None
            xe = ye = None

            while isdata(px, py):

                direction = flow[py, px]
                if direction == nodata or direction == noflow:
                    break

                x = int(np.log2(direction))

                py = py + ci[x]
                px = px + cj[x]

                if (px, py) in pixels:

                    downstream = pixels[(px, py)]
                    ide = fids[downstream]
                    xe, ye = coords[downstream]
                    break

            out_feature = QgsFeature()
            out_feature.setGeometry(feature.geometry())
            out_feature.setAttributes(feature.attributes() + [
                ide,
                xe,
                ye
            ])
            sink.addFeature(out_feature)


        return {
            self.OUTPUT: dest_id
        }