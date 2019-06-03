# -*- coding: utf-8 -*-

"""
Segmentation

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import processing
import os

from qgis.core import (
    QgsFeature,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterVectorDestination,
    QgsProcessingParameterNumber,
    QgsWkbTypes,
    QgsGeometry,
    QgsFeatureSink
)

from ..metadata import AlgorithmMetadata

class Segmentation(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Segmentation
    """

    METADATA = AlgorithmMetadata.read(__file__, 'Segmentation')

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    STEP = 'STEP'
    CENTERLINE = 'CENTERLINE'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Input features to segment'),
            [QgsProcessing.TypeVectorLine, QgsProcessing.TypeVectorPolygon]))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.CENTERLINE,
            self.tr('Centerline of the polygon to segment'),
            [QgsProcessing.TypeVectorLine],
            optional=True))
        
        self.addParameter(QgsProcessingParameterNumber(
            self.STEP,
            self.tr('Segmentation step'),
            defaultValue=25.0,
            minValue=0))

        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT,
            self.tr('Segmented features')))


    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.segStep = self.parameterAsDouble(parameters, self.STEP, context)
        self.layer = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        self.cl_layer = self.parameterAsVectorLayer(parameters, self.CENTERLINE, context)

        if self.segStep == 0:
            feedback.reportError(self.tr('Segmentation step is null'), True)
            return False
        
        if self.layer.wkbType() == QgsWkbTypes.Polygon or self.layer.wkbType() == QgsWkbTypes.MultiPolygon:
            if self.cl_layer == None:
                feedback.reportError(self.tr('Polygon segmentation requires a centerline'), True)
                return False

            if not(self.cl_layer.wkbType() == QgsWkbTypes.LineString or self.cl_layer.wkbType() == QgsWkbTypes.MultiLineString):
                feedback.reportError(self.tr('Unsupported centerline geometry type'), True)
                return False

            feedback.pushInfo(self.tr('Polygon segmentation'))
            self.input_type = 'Polygon'
            return True
 
        if self.layer.wkbType() == QgsWkbTypes.LineString or self.layer.wkbType() == QgsWkbTypes.MultiLineString:
            feedback.pushInfo(self.tr('LineString segmentation'))
            self.input_type = 'LineString'
            return True

        feedback.reportError(self.tr('Unsupported geometry type'), True)
        return False

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring
        
        if self.input_type == 'Polygon':

            feedback.pushInfo('Compute polygon DGOs...')
            axis = processing.run('qgis:fieldcalculator',
                    {
                        'INPUT': self.cl_layer,
                        'FIELD_NAME': 'AXIS_ID',
                        'FIELD_TYPE': 1,
                        'FIELD_LENGTH': 3,
                        'FIELD_PRECISION': 0,
                        'NEW_FIELD': True,
                        'FORMULA': '@row_number',
                        'OUTPUT': 'memory:'
                    }, context=context, feedback=feedback)

            if feedback.isCanceled():
                return {}

            DGOs = processing.run('fct:disaggregatepolygon',
                    {
                        'polygon': self.layer,
                        'centerline': axis['OUTPUT'],
                        'disagreggationdistance': str(self.segStep),
                        'axisfidfield': 'AXIS_ID',
                        'qgis:refactorfields_1:DISAGGREGATED': parameters['OUTPUT']
                    }, context=context, feedback=feedback)

            return {self.OUTPUT: DGOs['qgis:refactorfields_1:DISAGGREGATED']}

        elif self.input_type == 'LineString':

            feedback.pushInfo('Compute line DGOs...')
            segments = processing.run('fct:segmentize',
            {
                'DISTANCE': self.segStep,
                'INPUT': self.layer,
                'OUTPUT': parameters['OUTPUT']
            }, context=context, feedback=feedback)
            
            return {self.OUTPUT: segments['OUTPUT']}
