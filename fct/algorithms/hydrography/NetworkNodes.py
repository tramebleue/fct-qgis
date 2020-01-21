# -*- coding: utf-8 -*-

"""
NetworkNodes - Extract and categorize nodes from hydrogaphy network

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
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
from ..util import asQgsFields

def asPolyline(geometry):

    if geometry.isMultipart():
        return geometry.asMultiPolyline()[0]
    else:
        return geometry.asPolyline()

def node_type(in_degree, out_degree):
    """ Classify node based on in- and out-degree
    """

    if in_degree == 0:
        if out_degree == 0:
            typ = 'XOUT' # Exterior node (not included in graph construction)
        elif out_degree == 1:
            typ = 'SRCE' # Source node
        else:
            typ = 'DIVG' # Diverging node
    elif in_degree == 1:
        if out_degree == 0:
            typ = 'EXUT' # Outlet (exutoire)
        elif out_degree == 1:
            typ = 'NODE' # Simple node between 2 edges (reaches)
        else:
            typ = 'DIFL' # Diffluence
    else:
        if out_degree == 0:
            typ = 'XSIN' # Sink
        elif out_degree == 1:
            typ = 'CONF' # Confluence
        else:
            typ = 'XXOS' # Crossing

    return typ

class NetworkNodes(AlgorithmMetadata, QgsProcessingAlgorithm):
    """ Extract and categorize nodes from hydrogaphy network
    """

    METADATA = AlgorithmMetadata.read(__file__, 'NetworkNodes')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    MEAS_FIELD = 'MEAS_FIELD'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input linestrings'),
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
            self.MEAS_FIELD,
            self.tr('Measure Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='MEASURE',
            optional=True))

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Nodes'),
            QgsProcessing.TypeVectorPoint))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        measure_field = self.parameterAsString(parameters, self.MEAS_FIELD, context)

        feedback.pushInfo(self.tr("Build node index ..."))

        fields = [
            QgsField('GID', type=QVariant.Int, len=10),
            QgsField('DIN', type=QVariant.Int, len=6),
            QgsField('DOUT', type=QVariant.Int, len=6),
            QgsField('TYPE', type=QVariant.String, len=4),
            QgsField('MEAS', type=QVariant.Double, len=10, prec=2)
        ]

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            asQgsFields(*fields),
            QgsWkbTypes.Point,
            layer.sourceCrs())

        adjacency = dict()
        nodes = dict()

        total = 100.0 / layer.featureCount() if layer.featureCount() else 0

        for current, feature in enumerate(layer.getFeatures()):

            from_node = feature.attribute(from_node_field)
            to_node = feature.attribute(to_node_field)

            if measure_field:
                measure = feature.attribute(measure_field)
            else:
                measure = 0.0

            if from_node in adjacency:
                adjacency[from_node].append(to_node)
            else:
                adjacency[from_node] = [to_node]
                polyline = asPolyline(feature.geometry())
                nodes[from_node] = (polyline[0], measure)

            if to_node not in adjacency:
                adjacency[to_node] = list()
                polyline = asPolyline(feature.geometry())
                nodes[to_node] = (polyline[-1], measure - feature.geometry().length())

            feedback.setProgress(int(current * total))
            if feedback.isCanceled():
                break

        feedback.pushInfo(self.tr("Compute in-degree ..."))

        in_degree = dict()

        for node in adjacency:
            if node not in in_degree:
                in_degree[node] = 0
            for to_node in adjacency[node]:
                in_degree[to_node] = in_degree.get(to_node, 0) + 1

        feedback.pushInfo(self.tr("Output endpoints ..."))

        total = 100.0 / len(nodes) if nodes else 0

        for current, gid in enumerate(nodes.keys()):

            feature = QgsFeature()
            point, measure = nodes[gid]
            din = in_degree[gid]
            dout = len(adjacency[gid])
            feature.setGeometry(QgsGeometry.fromPointXY(point))
            feature.setAttributes([
                gid,
                din,
                dout,
                node_type(din, dout),
                measure
                ])

            sink.addFeature(feature)

            feedback.setProgress(int(current * total))
            if feedback.isCanceled():
                break

        return {self.OUTPUT: dest_id}
