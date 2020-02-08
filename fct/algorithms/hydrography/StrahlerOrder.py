# -*- coding: utf-8 -*-

"""
StrahlerOrder - Horton-Strahler stream order of each link in a stream network

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict, Counter

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingMultiStepFeedback,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField
)

from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

class StrahlerOrder(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Horton-Strahler stream order of each link in a stream network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'StrahlerOrder')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    AXIS_FIELD = 'AXIS_FIELD'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream network (polylines)'),
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

        self.addParameter(QgsProcessingParameterField(
            self.AXIS_FIELD,
            self.tr('Hack Order Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='HACK',
            optional=False))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Strahler Order'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, fb): #pylint: disable=unused-argument,missing-docstring

        feedback = QgsProcessingMultiStepFeedback(3, fb)

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        axis_field = self.parameterAsString(parameters, self.AXIS_FIELD, context)

        # Step 1 - Build adjacency index

        feedback.setCurrentStep(0)
        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        graph = defaultdict(list)
        indegree = Counter()
        axis_order = dict()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)
            axis = edge.attribute(axis_field) if axis_field else None

            graph[a].append((b, axis))
            indegree[b] += 1

            if b in axis_order:
                axis_order[b] = min(axis, axis_order[b])
            else:
                axis_order[b] = axis

            feedback.setProgress(int(current * total))

        # Step 3 - Prune sources/leaves iteratively

        feedback.setCurrentStep(1)
        feedback.setProgressText(self.tr("Enumerate links by Strahler order ..."))

        strahler_order = defaultdict(lambda: 1)

        sources = [node for node in graph if indegree[node] == 0]
        active_nodes = defaultdict(set)

        # n0 = {224128, 223943, 223944, 224007}

        while sources:

            if feedback.isCanceled():
                break

            source = sources.pop(0)
            order = strahler_order[source]

            # if source in n0:
            #     feedback.pushInfo('Pick source %d with order %d' % (source, order))

            for next_node, next_axis in graph[source]:

                # if next_node in n0:
                #     feedback.pushInfo(
                #         'Pick next node %d from %d with order %d and degree %d' %
                #         (next_node, source, strahler_order[next_node], indegree[next_node]))

                if next_node in active_nodes:

                    next_order = strahler_order[next_node]

                    if next_order == order:

                        if next_axis not in active_nodes[next_node]:

                            strahler_order[next_node] = order + 1
                            active_nodes[next_node].add(next_axis)

                    else:

                        strahler_order[next_node] = max(next_order, order)
                        active_nodes[next_node].add(next_axis)

                else:

                    strahler_order[next_node] = order
                    active_nodes[next_node].add(next_axis)

                indegree[next_node] -= 1

                # if next_node in n0:
                #     feedback.pushInfo(
                #         'Release node %d with order %d and degree %d' %
                #         (next_node, strahler_order[next_node], indegree[next_node]))

                if indegree[next_node] == 0:

                    del active_nodes[next_node]
                    sources.append(next_node)

        # Check that we have consumed all nodes
        # If not, some nodes have been trapped in loops ...
        # We can process only directed acyclic graphs.

        if sum(1 for node in graph if indegree[node] > 0) > 0:
            feedback.reportError(self.tr("There are loops in network !"), False)

        feedback.setCurrentStep(2)
        feedback.setProgressText(self.tr('Output features ...'))

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('STRAHLER', QVariant.Int, len=5), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        for current, edge in enumerate(layer.getFeatures()):

            a = edge.attribute(from_node_field)
            order = strahler_order[a]

            feature = QgsFeature()
            feature.setGeometry(edge.geometry())
            feature.setAttributes(edge.attributes() + [
                order
            ])
            sink.addFeature(feature)

            feedback.setProgress(int(current * total))

        return {self.OUTPUT: dest_id}
