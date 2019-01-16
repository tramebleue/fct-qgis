# -*- coding: utf-8 -*-

"""
Knick Points Detection

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class KnickPoints(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Knickpoints detection based on Relative Slope Extension Index (RSE)

        See:

        [1] Queiroz et al. (2015).
            Knickpoint finder: A software tool that improves neotectonic analysis.
            Computers & Geosciences, 76, 80‑87.
            https://doi.org/10.1016/j.cageo.2014.11.004

        [2] Knickpoint Finder, ArcGIS implementation
            http://www.neotectonica.ufpr.br/2013/index.php/aplicativos/doc_download/87-knickpointfinder
            No License
    """

    METADATA = AlgorithmMetadata.read(__file__, 'KnickPoints')

    INPUT = 'INPUT'
    NODATA = 'NODATA'
    MIN_DZ = 'MIN_DZ'
    MIN_RSE = 'MIN_RSE'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream Network Aggregated by Hack Order with Z Coordinate'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterNumber(
            self.NODATA,
            self.tr('No Data Value for Z')))

        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_DZ,
            self.tr('Contour Interval'),
            minValue=0.0,
            defaultValue=5.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_RSE,
            self.tr('Minimum Relative-Slope Extension Value for Knickpoints'),
            minValue=0.0,
            defaultValue=2.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Knickpoints'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        nodata = self.parameterAsDouble(parameters, self.NODATA, context)
        min_dz = self.parameterAsDouble(parameters, self.MIN_DZ, context)
        knickpoint_min_rse = self.parameterAsDouble(parameters, self.MIN_RSE, context)

        if not QgsWkbTypes.hasZ(layer.wkbType()):
            raise QgsProcessingException('Input features must have Z coordinate')

        fields = QgsFields(layer.fields())
        fields.append(QgsField('LENGTH', QVariant.Double, len=10, prec=2))
        fields.append(QgsField('UCL', QVariant.Double, len=10, prec=2))
        fields.append(QgsField('DZ', QVariant.Double, len=16, prec=12))
        fields.append(QgsField('RSE', QVariant.Double, len=16, prec=12))
        fields.append(QgsField('RSES', QVariant.Double, len=16, prec=12))
        fields.append(QgsField('RSET', QVariant.Double, len=16, prec=12))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            QgsWkbTypes.PointZ,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            geometry = feature.geometry()
            vertices = [v for v in geometry.vertices()]
            dz = vertices[0].z() - vertices[-1].z()
            # rse_total = dz / geometry.length() * max(0.0001, math.log(geometry.length()))
            rse_total = dz / max(0.0001, math.log(geometry.length()))
            # rse_total = dz / geometry.length()

            stretch_length = 0.0
            upstream_length = 0.0
            previous = vertices[0]

            for vertex in vertices[1:-1]:

                if feedback.isCanceled():
                    break

                dz = previous.z() - vertex.z()
                if dz < min_dz:
                    continue

                stretch_length += vertex.distance(previous)
                upstream_length += vertex.distance(previous)

                if stretch_length:

                    rse_stretch = dz/stretch_length * upstream_length
                    rse_index = rse_stretch / max(0.0001, rse_total)

                    if knickpoint_min_rse <= 0 or rse_index >= knickpoint_min_rse:

                        knickpoint = QgsFeature()
                        knickpoint.setGeometry(QgsGeometry(vertex))
                        knickpoint.setAttributes(feature.attributes() + [
                            stretch_length,
                            upstream_length,
                            dz,
                            rse_index,
                            rse_stretch,
                            rse_total
                        ])

                        sink.addFeature(knickpoint)

                    previous = vertex
                    stretch_length = 0.0

            feedback.setProgress(int(current*total))

        return {
            self.OUTPUT: dest_id
        }
