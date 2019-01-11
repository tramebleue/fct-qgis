# -*- coding: utf-8 -*-

"""
AggregateLineSegmentsByCat - Merge continuous line segments into a single linestring

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsExpression,
    QgsGeometry,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

def asPolyline(geometry):

    if geometry.isMultipart():
        return geometry.asMultiPolyline()[0]
    else:
        return geometry.asPolyline()

class FidGenerator(object):
    """ Generate a sequence of integers to be used as identifier
    """

    def __init__(self, start=0):
        self.x = start

    def __next__(self):
        self.x = self.x + 1
        return self.x

    @property
    def value(self):
        """ Current value of generator
        """
        return self.x

class AggregateLineSegments(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Merge continuous line segments into a single linestring
    """

    METADATA = AlgorithmMetadata.read(__file__, 'AggregateLineSegments')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    CATEGORY_FIELD = 'CATEGORY_FIELD'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    MEASURE_FIELD = 'MEASURE_FIELD'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input linestrings'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.CATEGORY_FIELD,
            self.tr('Category Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Any,
            optional=True))

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
            self.tr('Aggregated Lines'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        category_field = self.parameterAsString(parameters, self.CATEGORY_FIELD, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        measure_field = self.parameterAsString(parameters, self.MEASURE_FIELD, context)

        if category_field:
            category_field_idx = layer.fields().lookupField(category_field)
            category_field_instance = layer.fields().at(category_field_idx)
        else:
            category_field_instance = QgsField('CATEGORY', QVariant.String, len=16)

        fields = asQgsFields(
            QgsField('GID', type=QVariant.Int, len=10),
            category_field_instance,
            QgsField(from_node_field, type=QVariant.Int, len=10),
            QgsField(to_node_field, type=QVariant.Int, len=10),
            QgsField(measure_field, type=QVariant.Double, len=10, prec=2)
        )

        (sink, dest_id) = self.parameterAsSink(parameters, self.OUTPUT, context,
                                               fields, layer.wkbType(), layer.sourceCrs())

        fid = FidGenerator()
        categories = dict()

        def countCategories():
            """ List unique values in field `category_field`
                and count features by category
            """

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

        def processCategory(category=None):
            """ Aggregate segments of given category,
                or all segments if `category` is None
            """

            if feedback.isCanceled():
                return

            feedback.pushInfo(self.tr("Build node index ..."))

            adjacency = dict()
            feature_index = dict()

            if category is None:

                total = 100.0 / layer.featureCount() if layer.featureCount() else 0
                iterator = layer.getFeatures()

            else:

                total = 100.0 / categories[category]

                expression = QgsExpression('%s = %s' % (category_field, category))
                query = QgsFeatureRequest(expression)
                iterator = layer.getFeatures(query)

            for current, feature in enumerate(iterator):

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
                        category,
                        from_node,
                        next_node,
                        measure
                    ])
                    sink.addFeature(feature)

                    # dont't process twice or more after confluences
                    # if branch == 0:
                    # if not next_node in seen_nodes:
                    process_stack.append(next_node)


        if category_field:

            countCategories()

            for category in categories:
                processCategory(category)

        else:

            processCategory()

        feedback.pushConsoleInfo("Created %d line features" % fid.value)

        return {self.OUTPUT: dest_id}
