# -*- coding: utf-8 -*-

"""
***************************************************************************
    Sinuosity.py
    ---------------------
    Date                 : February 2018
    Copyright            : (C) 2018 by Christophe Rousson
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QgsFeature, QgsField, QgsPoint, QgsGeometry
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper

class Sinuosity(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Sinuosity')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Sinuosity')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                layer,
                QgsField('SINUOSITY', QVariant.Double, len=10, prec=6)
            ),
            layer.dataProvider().geometryType(),
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        def sinuosity(geom):

            length = geom.length()
            start = geom.interpolate(0.0)
            end = geom.interpolate(length)
            d = start.distance(end)

            if d > 0.0:

                return length / d

            else:

                return 1.0

        for current, feature in enumerate(features):

            geom = feature.geometry()
            length = geom.length()

            if length > 0.0:

                if geom.isMultipart():

                    s = 0.0

                    for part in geom.asMultiPolyline():

                        part_geom = QgsGeometry.fromPolyline(part)
                        s = s + part_geom.length() * sinuosity(part_geom)

                    s = s / length

                else:

                    s = sinuosity(geom)

            else:

                s = 1.0

            out_feature = QgsFeature(feature)
            out_feature.setAttributes(feature.attributes() + [
                    s
                ])
            writer.addFeature(out_feature)


            progress.setPercentage(int(current * total))