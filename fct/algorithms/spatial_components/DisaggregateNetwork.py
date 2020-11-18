# -*- coding: utf-8 -*-

"""
DisaggregateNetwork

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import os

from PyQt5.QtCore import QVariant
from qgis.core import (
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsWkbTypes,
    QgsField,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber,
    QgsProcessingParameterField,
    QgsFeatureRequest,
    QgsExpression,
    QgsVectorLayer,
    QgsGeometry,
    QgsFeature,
)

from ..metadata import AlgorithmMetadata


class DisaggregateNetwork(AlgorithmMetadata, QgsProcessingAlgorithm):

    METADATA = AlgorithmMetadata.read(__file__, "DisaggregateNetwork")

    NETWORK = "NETWORK"
    POLYGON = "POLYGON"
    AXIS_FID = "AXIS_FID"
    POLY_AXIS_FID = "POLY_AXIS_FID"
    STEP = "STEP"
    DISAGGREGATED = "DISAGGREGATED"

    def initAlgorithm(self, configuration):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.NETWORK,
                self.tr("Polyline network"),
                [QgsProcessing.TypeVectorLine],
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.AXIS_FID,
                self.tr("Network Axis FID field"),
                parentLayerParameterName=self.NETWORK,
                defaultValue="AXIS_FID",
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.POLYGON,
                self.tr("Polygons to disaggregate"),
                [QgsProcessing.TypeVectorPolygon],
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.POLY_AXIS_FID,
                self.tr("Polygons Axis FID field"),
                parentLayerParameterName=self.POLYGON,
                defaultValue="AXIS_FID",
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.STEP, self.tr("Disaggregation distance"), defaultValue=250
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.DISAGGREGATED, self.tr("Disaggregated polygons")
            )
        )

    def processAlgorithm(
        self, parameters, context, feedback
    ):  # pylint: disable=unused-argument,missing-docstring
        network = self.parameterAsSource(parameters, self.NETWORK, context)
        polygons = self.parameterAsSource(parameters, self.POLYGON, context)

        axis_fid_net = self.parameterAsFields(parameters, self.AXIS_FID, context)[0]
        axis_fid_poly = self.parameterAsFields(parameters, self.POLY_AXIS_FID, context)[0]
        idx_axis_net = network.fields().indexOf(axis_fid_net)
        idx_axis_poly = polygons.fields().indexOf(axis_fid_poly)

        step = self.parameterAsInt(parameters, self.STEP, context)

        fields = polygons.fields()
        fields.append(QgsField(name="POSITION", type=QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.DISAGGREGATED,
            context,
            fields,
            QgsWkbTypes.MultiPolygon,
            polygons.sourceCrs(),
        )
        
        net_axes = network.uniqueValues(idx_axis_net)
        poly_axes = polygons.uniqueValues(idx_axis_poly)
        axes = net_axes & poly_axes

        total = 100.0 / len(axes) if len(axes) else 0
        feedback.pushInfo(self.tr(f"{len(axes)} axes in both network and polygon data"))

        for current, axis_number in enumerate(axes):
            if feedback.isCanceled():
                feedback.reportError(self.tr("Aborted"), True)
                break

            network_features = network.getFeatures(
                request=QgsFeatureRequest(
                    QgsExpression(f"{axis_fid_net}={axis_number}")
                )
            )
            polygon_features = polygons.getFeatures(
                request=QgsFeatureRequest(
                    QgsExpression(f"{axis_fid_poly}={axis_number}")
                )
            )

            for polyline in network_features:
                #axis = polyline.geometry().simplify(step * 10).smooth(iterations=10)
                axis = polyline.geometry()
                length = axis.length()

                pts_list = []

                pos = step
                while pos < length:
                    pts_list.append(axis.interpolate(pos).asPoint())
                    pos += step

                line = QgsGeometry().fromPolylineXY(pts_list)

                for polygon in polygon_features:
                    poly_geom = polygon.geometry()
                    voronoi = line.voronoiDiagram(extent=poly_geom)
                    output = QgsFeature()

                    for dgo in voronoi.asGeometryCollection():
                        cut_dgo = dgo.intersection(poly_geom)
                        if cut_dgo:
                            output.setGeometry(cut_dgo)

                            loc = axis.lineLocatePoint(cut_dgo.centroid())
                            attr = polygon.attributes()
                            attr.append(loc)

                            output.setAttributes(attr)
                            sink.addFeature(output)

            feedback.setProgress(int(current * total))

        return {self.DISAGGREGATED: dest_id}
