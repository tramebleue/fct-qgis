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
    # QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum,
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
    'outlets_def'
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
    OUTLETS_DEFINITION = 'OUTLETS_DEFINITION'
    OUTPUT = 'OUTPUT'

    OUTLETS_DEF_MINZ = 0
    OUTLETS_DEF_SELECTION = 1
    OUTLETS_DEF_DANGLING = 2

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

        self.addParameter(QgsProcessingParameterEnum(
            self.OUTLETS_DEFINITION,
            self.tr('How To Define Outlets'),
            options=[self.tr(option) for option in [
                'Minimum-Z Node',
                'Selected Nodes',
                'Dangling Nodes']],
            defaultValue=0))

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
        outlets_def = self.parameterAsInt(parameters, self.OUTLETS_DEFINITION, context)

        if not QgsWkbTypes.hasZ(nodes.wkbType()):
            feedback.pushInfo(self.tr('Input nodes must have Z coordinate'))
            return False

        self.parameters = Parameters(
            layer, nodes, from_node_field, to_node_field,
            pk_field, dryrun, outlets_def)

        return True

    def findOutlets(self, feedback, node_index, queue):
        """ Find node with minimum Z in each connected component
        """

        total = len(queue)

        outlets = set()
        seen_nodes = set()
        components = 0
        current = 0

        while queue:

            if feedback.isCanceled():
                break

            minz, node = heappop(queue)

            if node in seen_nodes:
                continue

            outlets.add(node)
            stack = [node]

            while stack:

                if feedback.isCanceled():
                    break

                node = stack.pop()

                if node in seen_nodes:
                    continue

                seen_nodes.add(node)

                for fid, next_node in node_index[node]:

                    stack.append(next_node)

                    current += 1
                    feedback.setProgress(int(current * total))

            components += 1

        feedback.pushInfo(self.tr('Found %d connected components') % components)

        return outlets

    def processNetwork(self, parameters, context, feedback): #pylint: disable=unused-argument
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

        if self.parameters.outlets_def == self.OUTLETS_DEF_DANGLING:

            outlets = set(node for node in junctions if degree[node] == 1)

        elif self.parameters.outlets_def == self.OUTLETS_DEF_MINZ:

            outlets = self.findOutlets(feedback, node_index, list(queue))

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

        # Pick lowest-z node among remaining nodes,
        # and traverse graph until next junction

        while queue:

            if feedback.isCanceled():
                z, node = heappop(queue)
                print(z, node)
                break

            z, node = heappop(queue)
            if node in seen_nodes:
                continue

            if issink(node):

                sink = node

                # Shift node up in the queue
                # ie. set Z to higher a value than Z of next node,
                # and reinject into the queue

                z, node = heappop(queue)
                next_z, next_node = queue[0]
                heappush(queue, (z+max(0.05, 0.5*(next_z - z)), sink))
                heappush(queue, (z, node))

                continue

            # Depth-first, undirected graph traversal
            # starting from node, using a stack (last-in, first-out),
            # until the next junction

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
                        # We reached a junction, but we don't know the type of if
                        # (ie. if other links connected by this node come to it or leave from it)
                        # We'll continue from node when it is the lowest-z remaining node
                        degree[next_node] -= 1
                    else:
                        # Simple junction between two segments,
                        # we can traverse further
                        stack.append(next_node)

                    current += 1
                    feedback.setProgress(int(current * total))

        feedback.pushInfo('%d features need to be reversed' % len(marked))
        self.marked = marked

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.processNetwork(parameters, context, feedback)

        if self.parameters.dryrun:
            srclayer = context.getMapLayer(self.parameters.layer.sourceName())
            srclayer.selectByIds(list(self.marked), QgsVectorLayer.SetSelection)
            return {}

        # processFeature() for each feature in layer
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
