# -*- coding: utf-8 -*-

"""
PointsMedialAxis

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

from collections import namedtuple

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterField,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

PointAttributes = namedtuple('PointAttributes', ['id', 'axis', 'seq'])

def voronoi_transect(voronoi, attrs): # pylint: disable=too-many-locals
    """
    Extract Voronoi ridges equidistant of two points
    from the same axis and following each other on this axis.
    """

    for (p, q), rv in zip(voronoi.ridge_points, voronoi.ridge_vertices):

        u, v = sorted(rv)

        if u == -1 or attrs[p].axis != attrs[q].axis:
            continue

        if attrs[p].seq == 1256 or attrs[q].seq == 1256:
            print(p, q, u, v, voronoi.vertices[u], voronoi.vertices[v], attrs[p], attrs[q])

        if abs(attrs[p].seq - attrs[q].seq) == 1:

            vertex1 = voronoi.vertices[u]
            vertex2 = voronoi.vertices[v]
            yield (p, q, QgsGeometry(QgsLineString([QgsPoint(*vertex1), QgsPoint(*vertex2)])))

class VoronoiTransects(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Generate transects at equal distance between input points,
    based on the derived Voronoi diagram.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'VoronoiTransects')

    INPUT = 'INPUT'
    AXIS_FIELD = 'AXIS_FIELD'
    SEQ_FIELD = 'SEQ_FIELD'
    OUTPUT = 'OUTPUT'

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            from scipy.spatial import Voronoi
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.spatial')

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input Points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterField(
            self.AXIS_FIELD,
            self.tr('Axis Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='AXIS'))

        self.addParameter(QgsProcessingParameterField(
            self.SEQ_FIELD,
            self.tr('Sequence Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='SEQ'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Voronoi Transects'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from scipy.spatial import Voronoi #pylint: disable=no-name-in-module

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        axis_field = self.parameterAsString(parameters, self.AXIS_FIELD, context)
        seq_field = self.parameterAsString(parameters, self.SEQ_FIELD, context)

        fields = QgsFields()
        fields.append(QgsField('GID', QVariant.Int))
        fields.append(QgsField('AXIS', QVariant.Int))
        fields.append(QgsField('SEQ1', QVariant.Int))
        fields.append(QgsField('SEQ2', QVariant.Int))
        fields.append(QgsField('OX', QVariant.Double))
        fields.append(QgsField('OY', QVariant.Double))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            QgsWkbTypes.LineString,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        points = list()
        attrs = list()

        feedback.setProgressText(self.tr('Read input points'))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            if feature.geometry():

                points.append(feature.geometry().asPoint())
                attrs.append(PointAttributes(
                    feature.id(),
                    feature.attribute(axis_field),
                    feature.attribute(seq_field)
                ))

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr('Compute Voronoi polygons'))

        points = np.array([[p.x(), p.y()] for p in points])
        # see http://www.qhull.org/html/qh-optq.htm#QJn
        voronoi = Voronoi(points, qhull_options='Qbb Qc QJ')

        feedback.setProgressText(self.tr('Output medial axes'))

        total = 100.0 / voronoi.vertices.shape[0] if voronoi.vertices.shape[0] else 0

        for current, (p, q, ridge) in enumerate(voronoi_transect(voronoi, attrs)):

            if feedback.isCanceled():
                break

            x, y = 0.5 * (points[p] + points[q])

            feature = QgsFeature()
            feature.setGeometry(ridge)
            feature.setAttributes([
                current,
                attrs[p].axis,
                attrs[p].seq,
                attrs[q].seq,
                float(x),
                float(y)
            ])
            sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
