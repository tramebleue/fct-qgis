# -*- coding: utf-8 -*-

"""
FixLinkDirection - Check links are oriented downslope and reverse
    line geometries where needed.

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
from heapq import heappop, heappush

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsGeometry,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsVectorLayer,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

Parameters = namedtuple('Parameters', [
    'layer',
    'nodes',
    'from_node_field',
    'to_node_field',
    'pk_field',
    'dryrun',
    'selected_outlets'
])

class FixLinkOrientation(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Check links are oriented downslope.
        Wrongly oriented links can be either modified and reversed (default),
        or selected in the input layer.
        Input nodes must have Z coordinate (extracted from a DEM for example).
        Optionnaly, outlets can be specified
        by selecting relevant nodes in the node layer.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'FixLinkOrientation')

    INPUT = 'INPUT'
    NODES = 'NODES'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    NODE_PK_FIELD = 'NODE_PK_FIELD'
    DRYRUN = 'DRYRUN'
    SELECTED_OUTLETS = 'SELECTED_OUTLETS'
    OUTPUT = 'OUTPUT'

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterBoolean(
            self.DRYRUN,
            self.tr('Do Not Modify and Select Mis-Oriented Links'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODE_A'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODE_B'))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.NODES,
            self.tr('Nodes with Z coordinate'),
            [QgsProcessing.TypeVectorPoint]))

        self.addParameter(QgsProcessingParameterBoolean(
            self.SELECTED_OUTLETS,
            self.tr('Define Selected Nodes as Outlets'),
            defaultValue=False))

        self.addParameter(QgsProcessingParameterField(
            self.NODE_PK_FIELD,
            self.tr('Node Primary Key'),
            parentLayerParameterName=self.NODES,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='GID'))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Oriented Network')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring
        return inputWkbType

    # def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring
    #     return super().supportInPlaceEdit(layer)

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        nodes = self.parameterAsSource(parameters, self.NODES, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        pk_field = self.parameterAsString(parameters, self.NODE_PK_FIELD, context)
        dryrun = self.parameterAsBool(parameters, self.DRYRUN, context)
        selected_outlets = self.parameterAsBool(parameters, self.SELECTED_OUTLETS, context)

        if not QgsWkbTypes.hasZ(nodes.wkbType()):
            return False

        self.parameters = Parameters(
            layer, nodes, from_node_field, to_node_field,
            pk_field, dryrun, selected_outlets)

        return self.processNetwork(context, feedback)

    def processNetwork(self, context, feedback):
        """
        1. index links for undirected graph traversal
        2. sort nodes by z ascending
        3. traverse graph starting from node with lowest z
           and mark links not properly oriented
        """

        layer = self.parameters.layer
        nodes = self.parameters.nodes
        from_node_field = self.parameters.from_node_field
        to_node_field = self.parameters.to_node_field
        pk_field = self.parameters.pk_field

        # 1. index links for undirected graph traversal

        feedback.setProgressText(self.tr("Index links for undirected traversal ..."))

        # Index : Node -> List of edges connnected to Node
        node_index = defaultdict(list)
        degree = Counter()

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)
            degree[from_node] += 1
            degree[to_node] += 1

            node_index[from_node].append((feature.id(), to_node))
            node_index[to_node].append((feature.id(), from_node))

            feedback.setProgress(int(current * total))

        # 2. sort nodes by z ascending

        feedback.setProgressText(self.tr("Sort nodes by Z ascending ..."))
        total = 100.0 / nodes.featureCount() if nodes.featureCount() else 0
        queue = list()
        outlets = set()
        selected = context.getMapLayer(nodes.sourceName()).selectedFeatureIds()

        for current, feature in enumerate(nodes.getFeatures()):

            if feedback.isCanceled():
                break

            node = feature.attribute(pk_field)
            z = feature.geometry().vertexAt(0).z()
            heappush(queue, (z, node))

            if feature.id() in selected:
                outlets.add(node)

            feedback.setProgress(int(current * total))

        # 3. traverse graph starting from node with lowest z
        #    and mark links not properly oriented

        junctions = set(node for node in node_index if degree[node] != 2)
        if not self.parameters.selected_outlets:
            outlets = set(node for node in junctions if degree[node] == 1)
        marked = set()
        seen_nodes = set()
        seen_links = set()
        srclayer = context.getMapLayer(layer.sourceName())
        current = 0
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        # def meanz(neighbors):
        #     """ Return the mean Z of nodes in neighbors
        #     """

        #     return sum(zindex[node] for node in neighbors) / len(neighbors) \
        #         if neighbors else float('inf')

        def issink(node):
            """ Check if continued graph traversal from this node
                will create a new, unwanted sink
                (ie. no link will flow from this node).
                This happens when the difference in Z between nodes is small,
                due to the uncertainty (both horizontal or vertical)
                of the DEM that was used for extracting Z coordinates.
            """

            if node not in junctions:
                return True

            if node in outlets:
                return False

            for fid, next_node in node_index[node]:
                if fid in seen_links:
                    return False

            return True

        feedback.pushInfo('Start from z = %f with node %d' % queue[0])

        while queue:

            if feedback.isCanceled():
                break

            z, node = heappop(queue)
            if node in seen_nodes:
                continue

            if issink(node):
                # Shift node up in the queue
                # ie. set Z to higher a value than Z of next node,
                # and reinject into the queue
                sink = node
                z, node = heappop(queue)
                next_z, next_node = queue[0]
                heappush(queue, (z+max(0.05, 0.5*(next_z - z)), sink))
                heappush(queue, (z, node))
                continue

            stack = [node]

            while stack:

                if feedback.isCanceled():
                    break

                node = stack.pop()
                if node in seen_nodes:
                    continue

                seen_nodes.add(node)

                for fid, next_node in node_index[node]:

                    if fid in seen_links:
                        continue

                    seen_links.add(fid)

                    link = srclayer.getFeature(fid)
                    to_node = link.attribute(to_node_field)
                    if to_node != node:
                        marked.add(fid)

                    if degree[next_node] > 2:
                        degree[next_node] -= 1
                    else:
                        stack.append(next_node)

                    current += 1
                    feedback.setProgress(int(current * total))

        feedback.pushInfo('%d features need to be reversed' % len(marked))

        if self.parameters.dryrun:
            srclayer.selectByIds(list(marked), QgsVectorLayer.SetSelection)

        self.marked = marked
        return True

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        if self.parameters.dryrun:
            return {}

        return super().processAlgorithm(parameters, context, feedback)

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from_node_field = self.parameters.from_node_field
        to_node_field = self.parameters.to_node_field

        if feature.id() in self.marked:

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)
            feature.setAttribute(from_node_field, to_node)
            feature.setAttribute(to_node_field, from_node)

            polyline = feature.geometry().asPolyline()
            feature.setGeometry(QgsGeometry.fromPolylineXY(reversed(polyline)))

        return [feature]
