# -*- coding: utf-8 -*-

"""
***************************************************************************
    Gridify.py
    ---------------------
    Date                 : May 2010
    Copyright            : (C) 2010 by Michael Minn
    Email                : pyqgis at michaelminn dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Michael Minn'
__date__ = 'May 2010'
__copyright__ = '(C) 2010, Michael Minn'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'


from PyQt4.QtCore import QVariant
from qgis.core import QgsFields, QgsVectorLayer, QgsFeature

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.core.parameters import ParameterMultipleInput
from processing.core.outputs import OutputVector

from processing.tools import dataobjects, vector


class MergeGeometries(GeoAlgorithm):
    
    LAYERS = 'LAYERS'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Merge Geometries')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterMultipleInput(self.LAYERS,
                                                 self.tr('Layers to merge'), datatype=ParameterMultipleInput.TYPE_VECTOR_ANY))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Merged')))

    def processAlgorithm(self, progress):

        uris = self.getParameterValue(self.LAYERS)

        layers = []
        # fields = QgsFields()
        totalFeatureCount = 0

        for uri in uris.split(';'):

            layer = dataobjects.getObjectFromUri(uri)

            if (len(layers) > 0):

                if (layer.wkbType() != layers[0].wkbType()):
                    raise GeoAlgorithmExecutionException(
                        self.tr('All layers must have same geometry type!'))

                if (layer.crs() != layers[0].crs()):
                    raise GeoAlgorithmExecutionException(
                        self.tr('All layers must have same CRS!'))

            layers.append(layer)
            totalFeatureCount += layer.featureCount()

        total = 100.0 / totalFeatureCount
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            [],
            layers[0].wkbType(),
            layers[0].crs())

        featureCount = 0

        for layer in layers:

            for feature in layer.getFeatures():

                out_feature = QgsFeature()
                out_feature.setGeometry(feature.geometry())
                writer.addFeature(out_feature)
                featureCount += 1
                progress.setPercentage(int(featureCount * total))
