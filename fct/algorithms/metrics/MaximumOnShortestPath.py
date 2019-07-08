# -*- coding: utf-8 -*-

"""
Maximum On Shortest Path

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

from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module,import-error
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink,
    QgsFeature,
    QgsField,
    QgsFields
)

# from processing.core.ProcessingConfig import ProcessingConfig
from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField
from .graph_iterator import (
    GraphIterator,
    UndirectedEdgeLayerGraph,
    DirectedEdgeLayerGraph
)

class MaximumOnShortestPath(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Search nearest target from each input point,
    and record the maximum cost of the edges being traversed.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'MaximumOnShortestPath')

    INPUT = 'INPUT'
    NODE_LAYER = 'NODE_LAYER'
    PK_FIELD = 'PK_FIELD'
    NODE_TYPE_FIELD = 'NODE_TYPE_FIELD'

    # DISTANCE_FIELD = 'DISTANCE'
    # NHOPS_FIELD = 'NHOPS'
    # MAX_WEIGHT_FIELD = 'MAXW'

    EDGES = 'EDGES'
    GRAPH_TYPE = 'GRAPH_TYPE'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    WEIGHT_FIELD = 'WEIGHT_FIELD'
    # MAX_WEIGHT = 'MAX_WEIGHT'

    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Nodes'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Primary Key'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterField(
            self.NODE_TYPE_FIELD,
            self.tr('Node/Target Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='HYDRO'))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.EDGES,
            self.tr('Grpah/edges'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.EDGES,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='A'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.EDGES,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='B'))

        self.addParameter(QgsProcessingParameterField(
            self.WEIGHT_FIELD,
            self.tr('Weight Field'),
            parentLayerParameterName=self.EDGES,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='cost'))

        self.addParameter(QgsProcessingParameterEnum(
            self.GRAPH_TYPE,
            self.tr('Graph Type'),
            options=[self.tr(option) for option in ['Undirected', 'Directed']],
            defaultValue=0))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Maximum Cost'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        node_layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        type_field = self.parameterAsString(parameters, self.NODE_TYPE_FIELD, context)

        edge_layer = self.parameterAsVectorLayer(parameters, self.EDGES, context)
        node_a_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        node_b_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        graph_type = self.parameterAsInt(parameters, self.GRAPH_TYPE, context)

        weight_field = self.parameterAsString(parameters, self.WEIGHT_FIELD, context)
        # max_weight = self.getParameterValue(self.MAX_WEIGHT)
        max_weight = 60

        feedback.setProgressText(self.tr("Find target nodes ..."))

        targets = set()
        total = 100.0 / node_layer.featureCount()

        for current, target in enumerate(node_layer.getFeatures()):

            if feedback.isCanceled():
                break

            node_type = target.attribute(type_field)
            if node_type > 0:
                pk = target.attribute(pk_field)
                targets.add(pk)

            feedback.setProgress(int(current*total))

        feedback.pushInfo('Found %d target nodes' % len(targets))

        feedback.setProgressText(self.tr("Build graph ..."))

        if graph_type == 0:
            graph = UndirectedEdgeLayerGraph(edge_layer, node_a_field, node_b_field, weight_field, max_weight)
        else:
            graph = DirectedEdgeLayerGraph(edge_layer, node_a_field, node_b_field, weight_field, max_weight)

        feedback.setProgressText(self.tr("Compute shortest path to targets for each input node ..."))

        fields = QgsFields(node_layer.fields())

        appendUniqueField(QgsField('Distance', QVariant.Double), fields)
        appendUniqueField(QgsField('MaxCost', QVariant.Double), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            fields,
            node_layer.wkbType(),
            node_layer.sourceCrs())

        for current, feature in enumerate(node_layer.getFeatures()):

            if feedback.isCanceled():
                break

            node_type = feature.attribute(type_field)
            if node_type > 0:
                continue

            origin = feature.attribute(pk_field)

            with GraphIterator(graph, origin) as iterator:

                weight = np.infty
                entry = None

                for entry in iterator:

                    if feedback.isCanceled():
                        break

                    if entry.key in targets:
                        weight = entry.weight
                        break

                if weight != np.infty:

                    path, weight = iterator.path(entry.key)
                    # weights = [ iterator.seen[k].weight for k in path ]
                    # max_w = max([ weights[0] ] + [ weights[i+1] - w for i, w in enumerate(weights[:-1])  ])
                    outfeature = QgsFeature()
                    outfeature.setGeometry(feature.geometry())
                    outfeature.setAttributes(feature.attributes() + [
                        float(weight),
                        float(entry.max_cost)
                    ])
                    sink.addFeature(outfeature)

                else:

                    outfeature = QgsFeature()
                    outfeature.setGeometry(feature.geometry())
                    outfeature.setAttributes(feature.attributes() + [
                        None,
                        float(max_weight)
                    ])
                    sink.addFeature(outfeature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
