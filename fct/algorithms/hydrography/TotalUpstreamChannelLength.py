# -*- coding: utf-8 -*-

"""
UpstreamChannelLength - Compute a new `UCL` attribute
    as the total upstream channel length of each link.

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict, deque, namedtuple, Counter

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFeature,
    QgsField,
    QgsFields,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber
)

# from .graph import create_link_index
from ..metadata import AlgorithmMetadata
from ..util import appendUniqueField

Link = namedtuple('Link', ('id', 'a', 'b', 'length'))

class TotalUpstreamChannelLength(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute the total upstream channel length of each link;
    and store the result in a new attribute named `TUCL`.
    
    The implemented algorithm can process a complex network
    with diffluences.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'TotalUpstreamChannelLength')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    SCALE = 'SCALE'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream Network'),
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

        self.addParameter(QgsProcessingParameterNumber(
            self.SCALE,
            self.tr('Scale Factor'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=0.001))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Total Upstream Channel Length'),
            QgsProcessing.TypeVectorLine))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        scale = self.parameterAsDouble(parameters, self.SCALE, context)

        fields = QgsFields(layer.fields())
        appendUniqueField(QgsField('TUCL', QVariant.Double), fields)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields,
            layer.wkbType(),
            layer.sourceCrs())

        # Step 1 - Find sources and build adjacency index

        feedback.setProgressText(self.tr("Build adjacency index ..."))

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        # Directed graph: node A -connects to-> list of nodes B
        graph = defaultdict(list)
        inverse_graph = defaultdict(list)
        contributions = defaultdict(lambda: 0)
        outdegree = Counter()

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)

            length = edge.geometry().length()
            link = Link(edge.id(), a, b, length)
            graph[a].append(link)
            inverse_graph[b].append(link)
            outdegree[a] += 1

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Simplify graph ..."))

        # Create a simplified version of the network graph,
        # such as a node A links to only one node B.
        # When there is more than one possible link,
        # choose the longer one.

        outlets = {b for b in inverse_graph if outdegree[b] == 0}
        # Collect distance from outlet in `measures`
        measures = defaultdict(lambda: 0)
        simple_graph = dict()

        # Traverse graph from outlets to sources

        stack = list(outlets)
        seen_nodes = set()
        current = 0

        while stack:

            if feedback.isCanceled():
                break

            node = stack.pop()
            if node in seen_nodes:
                continue

            seen_nodes.add(node)
            measure = measures[node]

            # traverse graph until next diffluence

            for link in inverse_graph[node]:

                measure_a = measures[link.a]

                if measure_a < measure + link.length:
                    measures[link.a] = measure + link.length
                    simple_graph[link.a] = link

                # check if link.a is a diffluence
                if outdegree[link.a] > 1:
                    outdegree[link.a] -= 1
                    continue

                # otherwise process upward
                stack.append(link.a)

            current = current + 1
            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr("Identify secondary edges ..."))

        # Reverse simple_graph,
        # collect IDs of edges being traversed.
        # backtrack = {B: list of A nodes linking to B}

        backtrack = defaultdict(list)
        seen_edges = set()

        for a in simple_graph:
            link = simple_graph[a]
            contributions[link.b] += link.length
            seen_edges.add(link.id)
            backtrack[link.b].append(a)

        feedback.setProgressText(self.tr("Calculate secondary upstream length ..."))

        # indegree =
        # in-degree of node in the simplified graph
        indegree = defaultdict(lambda: 0)
        indegree.update({a: len(backtrack[a]) for a in backtrack})

        # sources in the simplified graph
        sources = {a for a in simple_graph if indegree[a] == 0}
        # junctions = {b for b in inverse_graph if len(inverse_graph[b]) > 0}

        # First, update the contributions of secondary sources,
        # as they have upstream links in the complete graph

        for source in sources:
            for link in inverse_graph[source]:
                contributions[source] += link.length
                seen_edges.add(link.id)

        # Then, traverse the complete graph from sources to outlets
        # and search for unvisited edges,
        # ie. secondary edges not being part of the simplified graph.

        # For each unvisited edge,
        # calculate the distance down to the next node on the simplified graph
        # and add this extra channel length to the contribution of the junction node.

        def set_extra_contribution(link):
            """
            Calculate distance from link to the next visited node
            """

            extra_contribution = contributions[link.b]
            stack = [link.b]

            while stack:

                if feedback.isCanceled():
                    break

                node = stack.pop()
                seen_nodes.add(node)

                if link.id in seen_edges:
                    break

                if node in simple_graph:

                    next_link = simple_graph[node]

                    # if next_link.b in junctions:

                    #     extra_contribution += next_link.length
                    #     contributions[next_link.b] += extra_contribution
                    #     seen_edges.add(next_link.id)
                    #     break

                    if next_link.b in seen_nodes:

                        contributions[next_link.b] += extra_contribution
                        seen_edges.add(next_link.id)
                        break

                    elif next_link.id not in seen_edges:

                        extra_contribution += next_link.length
                        seen_edges.add(next_link.id)
                        stack.append(next_link.b)

        # Breadth-first traversal from simplified graph sources

        stack = deque(sources)
        other_seen_nodes = set()

        while stack:

            if feedback.isCanceled():
                break

            a = stack.popleft()
            if a in other_seen_nodes:
                continue

            indegree[a] -= 1
            if indegree[a] > 0:
                continue

            other_seen_nodes.add(a)

            for link in graph[a]:

                if link.id not in seen_edges:
                    set_extra_contribution(link)
                    seen_edges.add(link.id)

                stack.append(link.b)

        feedback.setProgressText(self.tr("Accumulate ..."))

        # Breadth-first traversal from source to outlet
        # we want to update all upstream nodes
        # before we visit other nodes downstream.

        tucl = defaultdict(lambda: 0.0)
        queue = deque(sources)
        visited = 0

        # indegree =
        # in-degree of node in the simplified graph
        indegree = defaultdict(lambda: 0)
        indegree.update({a: len(backtrack[a]) for a in backtrack})

        while queue:

            if feedback.isCanceled():
                break

            a = queue.popleft()

            indegree[a] -= 1

            if indegree[a] > 0:
                continue

            visited += 1

            tucl[a] = contributions[a]
            for upstream in backtrack[a]:
                tucl[a] += tucl[upstream]

            if a in simple_graph:
                link = simple_graph[a]
                queue.append(link.b)

        feedback.pushInfo('Visited nodes : %d' % visited)

        feedback.setProgressText(self.tr("Output features ..."))

        current = 0
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, edge in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            a = edge.attribute(from_node_field)
            b = edge.attribute(to_node_field)

            if b == simple_graph[a].b:
                ucl = tucl[a] + edge.geometry().length()
            else:
                ucl = edge.geometry().length()

            out_feature = QgsFeature()
            out_feature.setGeometry(edge.geometry())
            out_feature.setAttributes(edge.attributes() + [
                scale*ucl
            ])

            sink.addFeature(out_feature)

            feedback.setProgress(int(current * total))

        return {
            self.OUTPUT: dest_id
        }
