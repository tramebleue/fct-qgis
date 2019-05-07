# -*- coding: utf-8 -*-

"""
Stream To Feature

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

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

# from processing.core.ProcessingConfig import ProcessingConfig
from ..metadata import AlgorithmMetadata

class StreamToFeature(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Vectorize Stream Features from Flow Direction/Accumulation Rasters
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StreamToFeature')

    FLOW = 'FLOW'
    FLOW_ACC = 'FLOW_ACC'
    MIN_ACC = 'MIN_ACC'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW_ACC,
            self.tr('Flow Accumulation')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_ACC,
            self.tr('Minimum Contributing Area (km2)'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0,
            defaultValue=5.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Vectorized Streams'),
            QgsProcessing.TypeVectorLine))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import stream_to_feature
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        # if ProcessingConfig.getSetting('FCT_ACTIVATE_CYTHON'):
        #     try:
        #         from ...lib.terrain_analysis import watershed
        #         with_cython = True
        #     except ImportError:
        #         from ...lib.watershed import watershed
        #         with_cython = False
        # else:
        #     from ...lib.watershed import watershed
        #     with_cython = False

        # if with_cython:
        #     feedback.pushInfo("Using Cython watershed() ...")
        # else:
        #     feedback.pushInfo("Using pure python watershed() - this may take a while ...")

        from ...lib.terrain_analysis import stream_to_feature

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        flow_acc_lyr = self.parameterAsRasterLayer(parameters, self.FLOW_ACC, context)
        min_acc = self.parameterAsDouble(parameters, self.MIN_ACC, context)

        flow_ds = gdal.OpenEx(flow_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        flow_acc_ds = gdal.OpenEx(flow_acc_lyr.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        flow_acc = flow_acc_ds.GetRasterBand(1).ReadAsArray()

        fields = QgsFields()
        fields.append(QgsField('GID', QVariant.Int))
        fields.append(QgsField('CONTAREA1', QVariant.Double, prec=3))
        fields.append(QgsField('CONTAREA2', QVariant.Double, prec=3))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineString,
            flow_lyr.crs())

        transform = flow_ds.GetGeoTransform()
        resolution_x = transform[1]
        resolution_y = -transform[5]
        threshold = min_acc * 1e6 / (resolution_x*resolution_y)

        streams = np.int16(flow_acc > threshold)
        streams[flow == -1] = -1

        def pixeltoworld(sequence):
            """ Transform raster pixel coordinates (px, py)
                into real world coordinates (x, y)
            """
            return (sequence + 0.5)*[transform[1], transform[5]] + [transform[0], transform[3]]

        for current, (segment, head) in enumerate(stream_to_feature(streams, flow, feedback=feedback)):

            if feedback.isCanceled():
                feedback.reportError(self.tr('Aborted'), True)
                return {}

            # if head and segment.shape[0] <= 2:
            #     continue

            j, i = segment[0]
            ca1 = flow_acc[i, j] / 1e6 * (resolution_x*resolution_y) 

            if segment.shape[0] > 2:
                j, i = segment[-2]
                ca2 = flow_acc[i, j] / 1e6 * (resolution_x*resolution_y)
            else:
                ca2 = ca1

            linestring = QgsGeometry.fromPolylineXY([
                QgsPointXY(x, y) for x, y in pixeltoworld(segment)
            ])

            feature = QgsFeature()
            feature.setAttributes([
                current,
                float(ca1),
                float(ca2)
            ])
            feature.setGeometry(linestring)
            sink.addFeature(feature)

        # Properly close GDAL resources
        flow_ds = None
        flow_acc_ds = None

        return {
            self.OUTPUT: dest_id
        }
