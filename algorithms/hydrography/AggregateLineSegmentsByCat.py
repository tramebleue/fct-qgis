# -*- coding: utf-8 -*-

"""
AggregateLineSegmentsByCat - Merge continuous line segments of the same category into a single linestring

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import (
    QVariant
)

from qgis.core import (
    QgsExpression,
    QgsGeometry,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata

def asPolyline(geometry):

    if geometry.isMultipart():
        return geometry.asMultiPolyline()[0]
    else:
        return geometry.asPolyline()

class IdGenerator(object):

    def __init__(self, start=0):
        self.x = start

    def __iter__(self):
        return self

    def __next__(self):
        self.x = self.x + 1
        return self.x

class AggregateLineSegmentsByCat(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Merge continuous line segments of the same category into a single linestring
    """

    METADATA = AlgorithmMetadata.read(__file__, 'AggregateLineSegmentsByCat')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    CATEGORY_FIELD = 'CATEGORY_FIELD'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    MEASURE_FIELD = 'MEASURE_FIELD'

    def initAlgorithm(self, configuration):

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input linestrings'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.CATEGORY_FIELD,
            self.tr('Category Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterField(
            self.MEASURE_FIELD,
            self.tr('Measure Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            optional=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Aggregated Lines'), QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback):

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        category_field = self.parameterAsString(parameters, self.CATEGORY_FIELD, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        measure_field = self.parameterAsString(parameters, self.MEASURE_FIELD, context)

        fields = QgsFields()

        for field in [
                QgsField('GID', type=QVariant.Int, len=10),
                QgsField(from_node_field, type=QVariant.Int, len=10),
                QgsField(to_node_field, type=QVariant.Int, len=10),
                QgsField(measure_field, type=QVariant.Double, len=10, prec=2)
            ]:

            fields.append(field)

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fields, layer.wkbType(), layer.sourceCrs())

        fid = IdGenerator()
        categories = dict()

        def countCategories():

            total = 100.0 / layer.featureCount() if layer.featureCount() else 0

            for current, feature in enumerate(layer.getFeatures()):

                if feedback.isCanceled():
                    break

                category = feature.attribute(category_field)
                if category in categories:
                    categories[category] = categories[category] + 1
                else:
                    categories[category] = 1

                feedback.setProgress(int(current * total))

        def processCategory(category):

            if feedback.isCanceled():
                return

            feedback.pushInfo(self.tr("Build node index ..."))

            adjacency = dict()
            feature_index = dict()

            total = 100.0 / categories[category]

            expression = QgsExpression('%s = %s' % (category_field, category))
            query = QgsFeatureRequest(expression)

            for current, feature in enumerate(layer.getFeatures(query)):

                if feedback.isCanceled():
                    break

                from_node = feature.attribute(from_node_field)
                to_node = feature.attribute(to_node_field)

                if measure_field:
                    measure = feature.attribute(measure_field)
                else:
                    measure = 0.0

                if from_node in adjacency:
                    adjacency[from_node].append(to_node)
                    feature_index[from_node].append(feature.id())
                else:
                    adjacency[from_node] = [to_node]
                    feature_index[from_node] = [feature.id()]

                if to_node not in adjacency:
                    adjacency[to_node] = list()
                    feature_index[to_node] = list()

                feedback.setProgress(int(current * total))

            feedback.pushInfo(self.tr("Compute in-degree ..."))

            in_degree = dict()
            for node in adjacency:
                if node not in in_degree:
                    in_degree[node] = 0
                for to_node in adjacency[node]:
                    in_degree[to_node] = in_degree.get(to_node, 0) + 1

            feedback.pushInfo(self.tr("Aggregate lines ..."))


            # Find source nodes
            process_stack = [
                node for node in adjacency
                if len(adjacency[node]) >= 1 and in_degree[node] == 0
            ]

            current = 0
            seen_nodes = set()
            srclayer = context.getMapLayer(layer.sourceName())

            while process_stack:

                if feedback.isCanceled():
                    break

                from_node = process_stack.pop()
                if from_node in seen_nodes:
                    continue
                seen_nodes.add(from_node)

                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Processing node %d" % from_node)

                for branch in range(0, len(adjacency[from_node])):

                    next_node = adjacency[from_node][branch]
                    next_segment_id = feature_index[from_node][branch]
                    segment = srclayer.getFeature(next_segment_id)
                    measure = segment.attribute(measure_field)
                    vertices = asPolyline(segment.geometry())

                    current = current + 1
                    feedback.setProgress(int(current * total))

                    while len(adjacency[next_node]) == 1 and in_degree[next_node] == 1:

                        next_segment_id = feature_index[next_node][0]
                        segment = srclayer.getFeature(next_segment_id)
                        vertices = vertices[:-1] + asPolyline(segment.geometry())

                        current = current + 1
                        feedback.setProgress(int(current * total))

                        next_node = adjacency[next_node][0]

                    feature = QgsFeature()
                    feature.setGeometry(QgsGeometry.fromPolylineXY(vertices))
                    feature.setAttributes([
                        next(fid),
                        from_node,
                        next_node,
                        measure
                    ])
                    sink.addFeature(feature)

                    # dont't process twice or more after confluences
                    # if branch == 0:
                    # if not next_node in seen_nodes:
                    process_stack.append(next_node)

        countCategories()

        for category in categories:
            processCategory(category)

        feedback.pushConsoleInfo("Created %d line features" % fid.x)

        return {self.OUTPUT: dest_id}
