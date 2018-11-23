# -*- coding: utf-8 -*-

"""
***************************************************************************
    GraphEndpoints.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant

import processing
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
import math

class InverseLongitudinalTransform(GeoAlgorithm):

    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'
    AXIS = 'AXIS'
    PK_FIELD = 'PK_FIELD'
    MEAS_FIELD = 'MEAS_FIELD'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Inverse Longitudinal Transform')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterVector(self.AXIS,
                                          self.tr('Reference Axis'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.PK_FIELD,
                                          self.tr('Linestrings-Axis Join Field'),
                                          parent=self.AXIS,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.MEAS_FIELD,
                                          self.tr('Measure Field'),
                                          parent=self.AXIS,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Untransformed')))


    def processAlgorithm(self, progress):

        layer = processing.getObject(self.getParameterValue(self.INPUT))
        axis_layer = processing.getObject(self.getParameterValue(self.AXIS))
        # from_node_field = self.getParameterValue(self.FROM_NODE_FIELD)
        # to_node_field = self.getParameterValue(self.TO_NODE_FIELD)
        pk_field = self.getParameterValue(self.PK_FIELD)
        measure_field = self.getParameterValue(self.MEAS_FIELD)

        axis_index = dict()
        total = 100.0 / axis_layer.featureCount()

        progress.setText(self.tr('Index Axis Layer ...'))

        for current, feature in enumerate(axis_layer.getFeatures()):

            pk = feature.attribute(pk_field)
            meas0 = feature.attribute(measure_field)
            axis_index[pk] = (feature.id(), meas0)

            progress.setPercentage(int(current * total))
        
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList(),
            layer.dataProvider().geometryType(),
            layer.crs())

        features = vector.features(layer)
        total = 100.0 / len(features)

        def inverse_transform(point, refaxis, meas0):
            """ Transform `point` back to its original position
            with respect to linear axis defined by `refaxis`.

            Parameters
            ----------

            point: QgsPoint
                Point to transform,
                with x coordinate the curvilinear location of original point along `refaxis`,
                and y coordinate the oriented distance of original point to `refaxis`

            refaxis: QgsGeometry, Polyline (LineString)
                2-points segment defining the x-axis of the transform

            meas0: float
                Start value for x-axis

            Returns
            -------

            The unstransformed point
            in the coordinate reference system of `refaxis`.
            """

            p0 = refaxis.interpolate(0.0).asPoint()
            p1 = refaxis.interpolate(refaxis.length()).asPoint()
            x0 = p0.x()
            y0 = p0.y()
            x1 = p1.x()
            y1 = p1.y()
            a = x1 - x0
            b = y1 - y0
            # det = p0.sqrDist(p1)
            det = a**2 + b**2
            length = math.sqrt(det)

            meas = point.x()
            distance = -point.y()
            # m = 1 - (meas - meas0) / refaxis.length()
            m = 1 - (meas - meas0) / length

            # (xp, yp) -> projection of point on refaxis
            xp = m*a + x0
            yp = m*b + y0
            
            # (x, y) -> original position
            x = xp - b*distance/length
            y = yp + a*distance/length

            return QgsPoint(x, y)

        progress.setText(self.tr('Transform Linestrings'))
        
        for current, feature in enumerate(features):

            pk = feature.attribute(pk_field)

            if axis_index.has_key(pk):
            
                axis_fid, meas0 = axis_index[pk]
                axis = axis_layer.getFeatures(QgsFeatureRequest(axis_fid)).next()
                axis_geom = axis.geometry()

                if axis_geom.length() > 0:

                    geom = QgsGeometry.fromPolyline([ inverse_transform(p, axis_geom, meas0) for p in feature.geometry().asPolyline() ])

                    feature.setGeometry(geom)
                    writer.addFeature(feature)

            # else:

            #     # log error

            progress.setPercentage(int(current * total))
