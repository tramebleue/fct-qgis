# -*- coding: utf-8 -*-

"""
ReverseFlowDirection - Reverse line direction and swap node fields

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import namedtuple

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsGeometry,
    QgsLineString,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterField,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

Parameters = namedtuple('Parameters', ['from_node_field', 'to_node_field'])

class ReverseFlowDirection(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Reverse line direction and swap node fields
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ReverseFlowDirection')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'

    def initParameters(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        # self.addParameter(QgsProcessingParameterFeatureSource(
        #     self.INPUT,
        #     self.tr('Stream Network'),
        #     [QgsProcessing.TypeVectorLine]))

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

        # self.addParameter(QgsProcessingParameterFeatureSink(
        #     self.OUTPUT,
        #     self.tr('Measured Links'),
        #     QgsProcessing.TypeVectorLine))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Reversed Links')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring
        return inputWkbType

    def supportInPlaceEdit(self, layer): #pylint: disable=no-self-use,missing-docstring
        return super().supportInPlaceEdit(layer) and QgsWkbTypes.isSingleType(layer.wkbType())

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        self.parameters = Parameters(from_node_field, to_node_field)

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        if feature.geometry().isMultipart():
            raise QgsProcessingException(self.tr('Input geometries must be single part'))

        from_node = feature.attribute(self.parameters.from_node_field)
        to_node = feature.attribute(self.parameters.to_node_field)
        geometry = QgsGeometry(QgsLineString(reversed([v for v in feature.geometry().vertices()])))

        feature[self.parameters.from_node_field] = to_node
        feature[self.parameters.to_node_field] = from_node
        feature.setGeometry(geometry)

        return [feature]
