# -*- coding: utf-8 -*-

"""
Cut and rotate polygon rings

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict

from qgis.core import ( # pylint: disable=import-error,no-name-in-module
    QgsGeometry,
    QgsFeatureRequest,
    QgsFeature,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsSpatialIndex,
    QgsVectorLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class CutAndRotateRing(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Cut polygon rings at given points, and return splitted linestrings.
    Rotate rings if necessary to avoid an extra split point at ring start/end.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'CutAndRotateRing')

    INPUT = 'INPUT'
    POINTS = 'POINTS'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input polygons'),
            [QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS,
            self.tr('Cut points'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Cut Rings'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        cut_layer = self.parameterAsSource(parameters, self.POINTS, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            layer.fields(),
            QgsWkbTypes.LineString,
            layer.sourceCrs())

        feedback.setProgressText(self.tr('Build ring points index'))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        temp_uri = "point?crs=%s&field=gid:integer&field=polygon:integer&field=ring:integer&field=vertex:integer" % layer.sourceCrs().authid().lower()
        temp_layer = QgsVectorLayer(temp_uri, "RingPoints", "memory")
        temp_layer.startEditing()
        gid = 1

        for current_polygon, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current_polygon * total))

            for current_ring, ring in enumerate(feature.geometry().asPolygon()):
                for current_vertex, vertex in enumerate(ring):

                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPointXY(vertex))
                    feature.setAttributes([
                        gid,
                        current_polygon,
                        current_ring,
                        current_vertex
                    ])
                    temp_layer.addFeature(feature)
                    gid += 1

        temp_layer.commitChanges()
        nearest_index = QgsSpatialIndex(temp_layer.getFeatures())
        match_index = defaultdict(list)

        feedback.setProgressText(self.tr('Match cut points with nearest ring'))
        total = 100.0 / cut_layer.featureCount() if cut_layer.featureCount() else 0

        for current_point, feature in enumerate(cut_layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current_point * total))

            point = feature.geometry().asPoint()
            request = QgsFeatureRequest().setFilterFids(nearest_index.nearestNeighbor(point, 1))

            for nearest in temp_layer.getFeatures(request):

                polygon_id = nearest.attribute('polygon')
                ring_id = nearest.attribute('ring')
                vertex = nearest.attribute('vertex')

                match_index[(polygon_id, ring_id)].append((vertex, point))

        feedback.setProgressText(self.tr('Cut/Rotate rings'))
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        def nearest_segment(ring, point, vertex):
            """
            Return nearest ring segment, as pair of vertex indices (before, after),
            and nearest point on this segment
            """

            point_geometry = QgsGeometry.fromPointXY(point)

            if vertex == 0:
                nearest_segment = QgsGeometry.fromPolylineXY(ring[vertex:vertex+2])
                before, after = (vertex, vertex+1)

            elif vertex == len(ring) - 1:
                nearest_segment = QgsGeometry.fromPolylineXY(ring[vertex-1:vertex+1])
                before, after = (vertex-1, vertex)

            else:

                segment_before = QgsGeometry.fromPolylineXY(ring[vertex-1:vertex+1])
                segment_after = QgsGeometry.fromPolylineXY(ring[vertex:vertex+2])

                if point_geometry.distance(segment_before) < point_geometry.distance(segment_after):
                    
                    nearest_segment = segment_before
                    before, after = (vertex-1, vertex)

                else:

                    nearest_segment = segment_after
                    before, after = (vertex, vertex+1)

            return (before, after), nearest_segment.nearestPoint(point_geometry).asPoint()

        for current_polygon, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current_polygon * total))

            for current_ring, ring in enumerate(feature.geometry().asPolygon()):

                cut_points = match_index[(current_polygon, current_ring)]

                if cut_points:

                    # sort by vertex order
                    cut_points = sorted(cut_points, key=lambda x: x[0])

                    vertex, point = cut_points[0]
                    (v1, v2), nearest_point = nearest_segment(ring, point, vertex)
                    new_ring = [nearest_point]

                    for vertex, point in cut_points[1:]:

                        (v3, v4), nearest_point = nearest_segment(ring, point, vertex)
                        new_ring.extend(ring[v2:v4])
                        new_ring.append(nearest_point)

                        new_feature = QgsFeature()
                        new_feature.setGeometry(QgsGeometry.fromPolylineXY(new_ring))
                        new_feature.setAttributes(feature.attributes())
                        sink.addFeature(new_feature)

                        v1, v2 = v3, v4
                        new_ring = [nearest_point]

                    # Rotate ring, make it starts and stops at first point
                    vertex, point = cut_points[0]
                    (v1, v2), nearest_point = nearest_segment(ring, point, vertex)
                    # Don't forget to skip last original point,
                    new_ring.extend(ring[v4:-1])
                    new_ring.extend(ring[:v2])
                    # and repeat first point as end of sequence
                    new_ring.append(nearest_point)

                    new_feature = QgsFeature()
                    new_feature.setGeometry(QgsGeometry.fromPolylineXY(new_ring))
                    new_feature.setAttributes(feature.attributes())
                    sink.addFeature(new_feature)

                    # new_ring = [point] + new_ring[v2+1:-1] + new_ring[:v2] + [point]

                else:

                    new_feature = QgsFeature()
                    new_feature.setGeometry(QgsGeometry.fromPolylineXY(ring))
                    new_feature.setAttributes(feature.attributes())
                    sink.addFeature(new_feature)

        return {self.OUTPUT: dest_id}
