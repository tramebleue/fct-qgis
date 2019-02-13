# -*- coding: utf-8 -*-

"""
Watershed Analysis

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

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
    QgsProcessingParameterRasterLayer,
    QgsWkbTypes
)

# from processing.core.ProcessingConfig import ProcessingConfig
from ..metadata import AlgorithmMetadata

class StreamToFeature(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Vectorize Stream Features
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StreamToFeature')

    FLOW = 'FLOW'
    STREAMS = 'STREAMS'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.STREAMS,
            self.tr('Streams Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.FLOW,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Vectorized Streams'),
            QgsProcessing.TypeVectorLine))

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

        from ...lib.streams import stream_to_feature

        flow_lyr = self.parameterAsRasterLayer(parameters, self.FLOW, context)
        streams_lyr = self.parameterAsRasterLayer(parameters, self.STREAMS, context)

        flow_ds = gdal.Open(flow_lyr.dataProvider().dataSourceUri())
        flow = flow_ds.GetRasterBand(1).ReadAsArray()

        streams_ds = gdal.Open(streams_lyr.dataProvider().dataSourceUri())
        streams = streams_ds.GetRasterBand(1).ReadAsArray()

        segments = stream_to_feature(streams, flow, feedback=feedback)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Output Features ...'))

        fields = QgsFields()
        fields.append(QgsField('GID', QVariant.Int, len=10))
        fields.append(QgsField('COUNT', QVariant.Int, len=10))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            QgsWkbTypes.LineString,
            streams_lyr.crs())

        total = 100.0 / len(segments) if segments else 0

        def pixeltoworld(sequence):
            """ Transform raster pixel coordinates (px, py)
                into real world coordinates (x, y)
            """
            tranform = streams_ds.GetGeoTransform()
            return (sequence + 0.5)*[tranform[1], tranform[5]] + [tranform[0], tranform[3]]

        for current, (segment, head) in enumerate(segments):

            if feedback.isCanceled():
                break

            if head and segment.shape[0] <= 2:
                continue

            linestring = QgsGeometry.fromPolylineXY([
                QgsPointXY(x, y) for x, y in pixeltoworld(segment)
            ])

            feature = QgsFeature()
            feature.setAttributes([
                current,
                segment.shape[0]
            ])
            feature.setGeometry(linestring)
            sink.addFeature(feature)

            feedback.setProgress(int(current*total))

        # Properly close GDAL resources
        flow_ds = None
        streams_ds = None

        return {
            self.OUTPUT: dest_id
        }
