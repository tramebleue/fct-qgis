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
from math import sqrt

class OrthogonalTransects(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    LENGTH = 'LENGTH'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Orthogonal Transects')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Segments'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterNumber(self.LENGTH,
                                          self.tr('Transect Length'),
                                          minValue=0.0, default=200.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Orthogonal Transects')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT))
        transect_length = self.getParameterValue(self.LENGTH)
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                layer
            ),
            layer.dataProvider().geometryType(),
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        def transect(segment, length):
            """
            Parameters
            ----------

            segment: QgsGeometry, (2-points) Polyline
            length: float, distance
                total length of transect to be generated
            """

            start_point = segment.interpolate(0.0).asPoint()
            end_point = segment.interpolate(segment.length()).asPoint()
            mid_point = segment.interpolate(0.5 * segment.length()).asPoint()

            a = end_point.x() - start_point.x()
            b = end_point.y() - start_point.y()
            d = sqrt(a**2 + b**2)
            normal = QgsPoint(-b / d, a / d)
            t1 = QgsPoint(mid_point.x() - 0.5*length*normal.x(), mid_point.y() - 0.5*length*normal.y())
            t2 = QgsPoint(mid_point.x() + 0.5*length*normal.x(), mid_point.y() + 0.5*length*normal.y())

            return QgsGeometry.fromPolyline([ t1, t2 ])

        for current, feature in enumerate(features):

            out_feature = QgsFeature(feature)
            geom = feature.geometry()

            if geom.length() > 0:

                transect_geom = transect(geom, transect_length)
                out_feature.setGeometry(transect_geom)
                out_feature.setAttributes(feature.attributes())
                writer.addFeature(out_feature)

            progress.setPercentage(int(current * total))