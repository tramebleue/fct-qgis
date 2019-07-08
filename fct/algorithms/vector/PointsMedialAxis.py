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

def medial_axis(voronoi, groups): # pylint: disable=too-many-locals
    """
    Extract Voronoi vertices equidistant of two points
    from two different groups.
    """

    for (p, q), rv in zip(voronoi.ridge_points, voronoi.ridge_vertices):

        u, v = sorted(rv)

        if u == -1 or groups[p] == groups[q]:
            continue

        vertex1 = voronoi.vertices[u]
        vertex2 = voronoi.vertices[v]
        yield (p, q, QgsGeometry(QgsLineString([QgsPoint(*vertex1), QgsPoint(*vertex2)])))

class PointsMedialAxis(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Generate a Medial Axis between two or more set of points.
        Input sets should be differentiated by a specified attribute.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'PointsMedialAxis')

    INPUT = 'INPUT'
    GROUP_FIELD = 'GROUP_FIELD'
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
            self.GROUP_FIELD,
            self.tr('Group Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Medial Axis'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from scipy.spatial import Voronoi #pylint: disable=no-name-in-module

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        group_field = self.parameterAsString(parameters, self.GROUP_FIELD, context)

        fields = QgsFields()
        fields.append(QgsField('GID', QVariant.Int, prec=10))
        fields.append(QgsField('NODE1', QVariant.Int, prec=10))
        fields.append(QgsField('NODE2', QVariant.Int, prec=10))

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            QgsWkbTypes.LineString,
            layer.sourceCrs())

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        points = list()
        groups = list()

        feedback.setProgressText(self.tr('Read input points'))

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            if feature.geometry():
                points.append((feature.id(), feature.geometry().asPoint()))
                groups.append(feature.attribute(group_field))

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr('Compute Voronoi polygons'))

        # see http://www.qhull.org/html/qh-optq.htm#QJn
        voronoi = Voronoi(np.array([[p.x(), p.y()] for i, p in points]), qhull_options='Qbb Qc QJ')

        feedback.setProgressText(self.tr('Output medial axes'))

        total = 100.0 / voronoi.vertices.shape[0] if voronoi.vertices.shape[0] else 0

        for current, (p, q, ridge) in enumerate(medial_axis(voronoi, groups)):

            if feedback.isCanceled():
                break

            feature = QgsFeature()
            feature.setGeometry(ridge)
            feature.setAttributes([
                current,
                points[p][0],
                points[q][0]
            ])
            sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
