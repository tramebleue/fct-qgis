# -*- coding: utf-8 -*-

"""
Variable-Width Vertex-Wise Buffer

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsExpression,
    QgsExpressionContextScope,
    QgsFeature,
    QgsLineString,
    QgsPoint,
    QgsProcessing,
    QgsProcessingException,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterEnum,
    QgsProcessingParameterExpression,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class TransformCoordinateByExpression(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Transform Z or M coordinate using an expression that is evaluated for each input vertex.

    The expression can include coordinates, and other fields values :
    - var('x') : vertex X coordinate
    - var('y') : vertex Y coordinate
    - var('z') : vertex Z coordinate
    - var('m') : vertex M coordinate
    - var('vertex') : vertex index
    """

    METADATA = AlgorithmMetadata.read(__file__, 'TransformCoordinateByExpression')

    EXPRESSION = 'EXPRESSION'
    STORE = 'STORE'

    STORE_M = 0
    STORE_Z = 1

    def initParameters(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterExpression(
            self.EXPRESSION,
            self.tr('Expression'),
            parentLayerParameterName='INPUT',
            defaultValue="var('vertex')"))

        # self.addParameter(QgsProcessingParameterString(
        #     self.EXPRESSION,
        #     self.tr('Expression'),
        #     defaultValue='vertex'))

        self.addParameter(QgsProcessingParameterEnum(
            self.STORE,
            self.tr('Store Result In'),
            options=[self.tr(option) for option in ['M', 'Z']],
            defaultValue=0))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Transformed')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,unused-argument,missing-docstring
        return QgsWkbTypes.LineStringZM

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return False

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        store = self.parameterAsInt(parameters, self.STORE, context)

        self.expression_context = self.createExpressionContext(parameters, context)
        self.zm_scope = QgsExpressionContextScope()

        for variable in ('x', 'y', 'z', 'm', 'vertex'):
            var = QgsExpressionContextScope.StaticVariable(
                variable, 0.0,
                readOnly=False,
                isStatic=False)
            self.zm_scope.addVariable(var)
        self.expression_context.appendScope(self.zm_scope)

        self.store_m = (store == self.STORE_M)

        context.setExpressionContext(self.expression_context)

        self.expression = QgsExpression(self.parameterAsExpression(parameters, self.EXPRESSION, context))
        if self.expression.hasParserError():
            feedback.reportError(self.expression.parserErrorString())
            return False

        self.expression.prepare(self.expression_context)

        return True

    def transform(self, geometry):
        """
        Evaluate input expression for each vertex,
        and store the result into M coordinate.
        Returns QgsLineString
        """

        vertices = list()

        for i, vertex in enumerate(geometry.vertices()):

            self.zm_scope.setVariable('x', vertex.x())
            self.zm_scope.setVariable('y', vertex.y())
            self.zm_scope.setVariable('z', vertex.z())
            self.zm_scope.setVariable('m', vertex.m())
            self.zm_scope.setVariable('vertex', i)

            value = self.expression.evaluate(self.expression_context)
            if self.expression.hasEvalError():
                raise QgsProcessingException(
                    self.tr('Evaluation error: {0}').format(self.expression.evalErrorString()))

            if self.store_m:
                vertices.append(QgsPoint(vertex.x(), vertex.y(), vertex.z(), value))
            else:
                vertices.append(QgsPoint(vertex.x(), vertex.y(), value, vertex.m()))

        return QgsLineString(vertices)

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        features = []

        for geometry in feature.geometry().asGeometryCollection():
            new_geometry = self.transform(geometry)
            new_feature = QgsFeature()
            new_feature.setAttributes(feature.attributes())
            new_feature.setGeometry(new_geometry)
            features.append(new_feature)

        return features
