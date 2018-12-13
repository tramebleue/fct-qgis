# -*- coding: utf-8 -*-

"""
***************************************************************************
    RemoveSmallPolygonalObjects.py
    ---------------------
    Date                 : November 2016
    Copyright            : (C) 2016 by Christophe Rousson
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Christophe Rousson'
__date__ = 'November 2016'
__copyright__ = '(C) 2016, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterVectorLayer,
                       QgsProcessingParameterVectorDestination,
                       QgsProcessingParameterField,
                       QgsProcessingParameterNumber)

import processing


class RemoveSmallPolygonalObjects(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    FIELD = 'FIELD'
    VALUE = 'VALUE'
    MIN_AREA = 'MIN_AREA'
    MIN_HOLE_AREA = 'MIN_HOLE_AREA'

    def initAlgorithm(self, config):

        self.addParameter(QgsProcessingParameterVectorLayer(self.INPUT, 
                                        self.tr('Input vector layer')))
        self.addParameter(QgsProcessingParameterVectorDestination(self.OUTPUT, 
                                        self.tr('Output vector layer')))
        self.addParameter(QgsProcessingParameterField(self.FIELD, 
                                        self.tr('Selection field'), parentLayerParameterName=self.INPUT))
        self.addParameter(QgsProcessingParameterNumber(self.VALUE, 
                                        self.tr('Selection value'), defaultValue=1))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_AREA, 
                                        self.tr('Minimum polygon area'), defaultValue=50e4, minValue=0))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_HOLE_AREA, 
                                        self.tr('Minimum hole area'), defaultValue=10e4, minValue=0))

    def processAlgorithm(self, parameters, context, feedback):
        INPUT = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        OUTPUT = self.parameterAsVectorDestination(parameters, self.OUTPUT, context)
        FIELD = self.parameterAsField(parameters, self.FIELD, context)
        VALUE = self.parameterAsInt(parameters, self.VALUE, context)
        MIN_AREA = self.parameterAsDouble(parameters, self.MIN_AREA, context)
        MIN_HOLE_AREA = self.parameterAsDouble(parameters, self.MIN_HOLE_AREA, context)

        feedback.pushInfo('Removing unselected objects...')
        SelectedObjects = processing.run('native:extractbyexpression',
                        {
                            'INPUT': INPUT,
                            'EXPRESSION': '%s = %f' % (FIELD, VALUE),
                            'OUTPUT': 'memory:'
                        })
        
        feedback.pushInfo('Removing small objects...')
        RemovedSmallObjects = processing.run('native:extractbyexpression',
                        {
                            'INPUT': SelectedObjects['OUTPUT'],
                            'EXPRESSION': '$area >= %f' % (MIN_AREA),
                            'OUTPUT': 'memory:'
                        })

        feedback.pushInfo('Removing small holes...')
        RemovedHoles = processing.run('native:deleteholes',
                        {
                            'INPUT': RemovedSmallObjects['OUTPUT'],
                            'MIN_AREA': MIN_HOLE_AREA,
                            'OUTPUT': 'memory:'
                        })

        return {self.OUTPUT: RemovedHoles['OUTPUT']}

    def name(self):
      return 'RemoveSmallPolygonalObjects'

    def groupId(self):
      return 'fctvectortools'

    def displayName(self):
      return self.tr(self.name())

    def group(self):
      return self.tr('Tools for Vectors')

    def tr(self, string):
        return QCoreApplication.translate('FluvialCorridorToolbox', string)

    def createInstance(self):
        return RemoveSmallPolygonalObjects()
