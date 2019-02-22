# -*- coding: utf-8 -*-

"""
Connect Lines

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import Counter, defaultdict, namedtuple

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsSpatialIndex
)

from ..metadata import AlgorithmMetadata

ClosestPointWithContext = namedtuple('ClosestPointWithContext', [
    'distance',
    'nearest_point',
    'vertex_after',
    'side'
])

class ConnectLines(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Connect lines by projecting end nodes to the nearest line.

    Lines must have been preprocessed with the tool `IdentifyNetworkNodes`
    or such a tool, and have end nodes identifiers.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ConnectLines')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    SEARCH_DISTANCE = 'SEARCH_DISTANCE'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Polylines'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        self.addParameter(QgsProcessingParameterDistance(
            self.SEARCH_DISTANCE,
            self.tr('Search Distance'),
            parentParameterName=self.INPUT,
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Connected Lines'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        search_distance = self.parameterAsDouble(parameters, self.SEARCH_DISTANCE, context)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs())

        feedback.setProgressText(self.tr("Build node index ..."))

        # Index : Node ID -> Point Geometry
        node_index = dict()
        degree = Counter()

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)
            degree[from_node] += 1
            degree[to_node] += 1

            if from_node not in node_index:
                point = feature.geometry().interpolate(0.0)
                node_index[from_node] = point

            if to_node not in node_index:
                point = feature.geometry().interpolate(feature.geometry().length())
                node_index[to_node] = point

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Match nodes with nearest lines ..."))

        spatial_index = QgsSpatialIndex(layer.getFeatures())
        modified_features = defaultdict(list)

        total = 100.0 / len(node_index) if len(node_index) else 0

        for current, node in enumerate(node_index):

            if feedback.isCanceled():
                break

            point = node_index[node]
            search_box = point.boundingBox()
            search_box.grow(search_distance)

            request = QgsFeatureRequest().setFilterFids(spatial_index.intersects(search_box))
            min_distance = float('inf')
            nearest_feature = None

            for feature in layer.getFeatures(request):

                from_node = feature.attribute(from_node_field)
                to_node = feature.attribute(to_node_field)

                if from_node == node or to_node == node:
                    continue

                distance = point.distance(feature.geometry())
                if distance <= search_distance and distance < min_distance:
                    min_distance = distance
                    nearest_feature = feature

            if nearest_feature:

                modified_features[nearest_feature.id()].append(node)

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Split features ..."))

        request = QgsFeatureRequest().setFilterFids([fid for fid in modified_features])
        total = 100.0 / len(modified_features) if len(modified_features) else 0
        node_id_seq = max(node for node in node_index) + 1

        for current, feature in enumerate(layer.getFeatures(request)):

            if feedback.isCanceled():
                break

            geometry = feature.geometry()

            split_points = [
                (node, ClosestPointWithContext(
                    *geometry.closestSegmentWithContext(node_index[node].asPoint())))
                for node in modified_features[feature.id()]
            ]

            split_points = sorted(
                [(node, point) for node, point in split_points],
                key=lambda p: p[1].vertex_after)

            start = 0
            start_node = feature.attribute(from_node_field)
            points = feature.geometry().asPolyline()

            for node, closest in split_points:

                point = node_index[node].asPoint()
                point_after = points[closest.vertex_after]

                # 4 cases :
                #   1. nearest_point is coincident with points[0], vertex_after=1
                #   2. nearest_point is points[vertex_after]
                #      (coincident vertex other than points[0])
                #   3. nearest_point is within a segment, between vertex_after-1 and vertex_after
                #   4. nearest_point is coincident with points[-1]

                if point_after.sqrDist(closest.nearest_point) > 0:

                    # case 1 : don't split, just join node to line

                    if closest.nearest_point.sqrDist(points[0]) > 0:

                        # case 3, split segment in two

                        new_feature = QgsFeature(feature)
                        new_feature.setGeometry(
                            QgsGeometry.fromPolylineXY(
                                points[start:closest.vertex_after] + [closest.nearest_point]))
                        new_feature.setAttribute(from_node_field, start_node)
                        new_feature.setAttribute(to_node_field, node_id_seq)
                        sink.addFeature(new_feature)

                        # insert nearest_point in point sequence
                        start = closest.vertex_after-1
                        points[start] = closest.nearest_point
                        start_node = node

                else:

                    # case 2, split at coincident vertex
                    # case 4, split, we'll get only one part, to_node gets a new ID

                    new_feature = QgsFeature(feature)
                    # +1 : repeat vertex_after
                    new_feature.setGeometry(
                        QgsGeometry.fromPolylineXY(
                            points[start:closest.vertex_after+1]))
                    new_feature.setAttribute(from_node_field, start_node)
                    new_feature.setAttribute(to_node_field, node_id_seq)
                    sink.addFeature(new_feature)

                    start = closest.vertex_after
                    start_node = node

                if closest.distance > 0:

                    # join node to splitted line

                    new_feature = QgsFeature(feature)
                    new_feature.setGeometry(
                        QgsGeometry.fromPolylineXY([point, closest.nearest_point]))
                    new_feature.setAttribute(from_node_field, node)
                    new_feature.setAttribute(to_node_field, node_id_seq)
                    sink.addFeature(new_feature)

                node_id_seq += 1

            if start < len(points)-1:

                new_feature = QgsFeature(feature)
                new_feature.setGeometry(
                    QgsGeometry.fromPolylineXY(points[start:]))
                new_feature.setAttribute(from_node_field, start_node)
                sink.addFeature(new_feature)

            feedback.setProgress(int(current * total))

        feedback.pushInfo(self.tr('%d input lines have been splitted.') % len(modified_features))

        feedback.setProgressText(self.tr("Output unmodified features ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            if feature.id() not in modified_features:
                sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
