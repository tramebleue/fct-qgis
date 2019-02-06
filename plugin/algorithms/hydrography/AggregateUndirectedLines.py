# -*- coding: utf-8 -*-

"""
AggregateLines

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import (
    Counter,
    defaultdict,
    namedtuple
)

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsExpression,
    QgsLineString,
    QgsFeature,
    QgsFeatureRequest,
    QgsField,
    QgsMultiLineString,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields, FidGenerator

Link = namedtuple('Link', ['node', 'other', 'feature_id'])

class AggregateUndirectedLines(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Merge continuous line segments into a single linestring
    """

    METADATA = AlgorithmMetadata.read(__file__, 'AggregateUndirectedLines')

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
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Aggregated Lines'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        category_field = self.parameterAsString(parameters, self.CATEGORY_FIELD, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)

        if category_field:
            category_field_idx = layer.fields().lookupField(category_field)
            category_field_instance = layer.fields().at(category_field_idx)
        else:
            category_field_instance = QgsField('CATEGORY', QVariant.String, len=16)

        fields = asQgsFields(
            QgsField('GID', type=QVariant.Int, len=10),
            QgsField('LENGTH', type=QVariant.Double, len=10, prec=2),
            category_field_instance
        )

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            QgsWkbTypes.MultiLineString,
            layer.sourceCrs())

        fid = FidGenerator()
        categories = Counter()

        def countCategories():
            """ List unique values in field `category_field`
                and count features by category
            """

            total = 100.0 / layer.featureCount() if layer.featureCount() else 0

            for current, feature in enumerate(layer.getFeatures()):

                if feedback.isCanceled():
                    break

                category = feature.attribute(category_field)
                categories[category] += 1

                feedback.setProgress(int(current * total))

        def processCategory(category=None):
            """ Aggregate segments of given category,
                or all segments if `category` is None
            """

            if feedback.isCanceled():
                return

            feedback.pushInfo(self.tr("Build node index ..."))

            link_index = defaultdict(list)
            degree = Counter()

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
                link_index[from_node].append(Link(from_node, to_node, feature.id()))
                link_index[to_node].append(Link(to_node, from_node, feature.id()))
                degree[from_node] += 1
                degree[to_node] += 1

                # if measure_field:
                #     measure = feature.attribute(measure_field)
                # else:
                #     measure = 0.0

                feedback.setProgress(int(current * total))

            feedback.pushInfo(self.tr("Aggregate lines ..."))

            # Find dangling nodes
            process_stack = [node for node in link_index if degree[node] == 1]

            current = 0
            seen_nodes = set()
            seen_links = set()
            srclayer = context.getMapLayer(layer.sourceName())

            while process_stack:

                if feedback.isCanceled():
                    break

                node = process_stack.pop()
                if node in seen_nodes:
                    continue

                seen_nodes.add(node)

                for link in link_index[node]:

                    if feedback.isCanceled():
                        break

                    if link.feature_id in seen_links:
                        continue

                    segment = srclayer.getFeature(link.feature_id)
                    linestring = QgsLineString([v for v in segment.geometry().vertices()])
                    geometry = QgsMultiLineString()
                    geometry.addGeometry(linestring.clone())

                    seen_links.add(link.feature_id)
                    current = current + 1
                    feedback.setProgress(int(current * total))

                    while degree[link.other] == 2:

                        if feedback.isCanceled():
                            break

                        next_link = link_index[link.other][0]

                        if next_link.feature_id in seen_links:
                            next_link = link_index[link.other][1]

                        if next_link.feature_id in seen_links:
                            break

                        segment = srclayer.getFeature(next_link.feature_id)
                        linestring = QgsLineString([v for v in segment.geometry().vertices()])
                        geometry.addGeometry(linestring.clone())

                        current = current + 1
                        feedback.setProgress(int(current * total))

                        seen_links.add(next_link.feature_id)
                        link = next_link

                    for part in geometry.mergeLines().asGeometryCollection():

                        feature = QgsFeature()
                        feature.setGeometry(part)
                        feature.setAttributes([
                            next(fid),
                            part.length(),
                            category
                        ])
                        sink.addFeature(feature)

                    process_stack.append(next_link.other)


        if category_field:

            countCategories()

            for category in categories:
                processCategory(category)

        else:

            processCategory()

        feedback.pushInfo("Created %d line features" % fid.value)

        return {self.OUTPUT: dest_id}
