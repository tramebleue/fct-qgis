# -*- coding: utf-8 -*-

"""
***************************************************************************
    JoinByNearest.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFeatureRequest, QgsFields
from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils, QgsDistanceArea, QgsProject, GEO_NONE
from qgis.utils import iface
import processing
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.parameters import ParameterString
from processing.core.outputs import OutputVector
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.tools import dataobjects, vector
from math import sqrt


class UpdateFieldByExpressionInPlace(GeoAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    FORMULA = 'FORMULA'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Update Field By Expression In Place')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterTableField(self.FIELD,
                                          self.tr('Target Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterString(self.FORMULA, self.tr('Formula')))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Updated'), True))

    def processAlgorithm(self, progress):

        layer = processing.getObject(self.getParameterValue(self.INPUT))
        target_field = self.getParameterValue(self.FIELD)
        formula = self.getParameterValue(self.FORMULA)

        # writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
        #     layer.fields().toList(),
        #     layer.dataProvider().geometryType(),
        #     layer.crs())

        target_field_idx = vector.resolveFieldIndex(layer, target_field)

        exp = QgsExpression(formula)

        da = QgsDistanceArea()
        da.setSourceCrs(layer.crs().srsid())
        da.setEllipsoidalMode(
            iface.mapCanvas().mapSettings().hasCrsTransformEnabled())
        da.setEllipsoid(QgsProject.instance().readEntry(
            'Measure', '/Ellipsoid', GEO_NONE)[0])
        
        exp.setGeomCalculator(da)
        exp.setDistanceUnits(QgsProject.instance().distanceUnits())
        exp.setAreaUnits(QgsProject.instance().areaUnits())

        exp_context = QgsExpressionContext()
        exp_context.appendScope(QgsExpressionContextUtils.globalScope())
        exp_context.appendScope(QgsExpressionContextUtils.projectScope())
        exp_context.appendScope(QgsExpressionContextUtils.layerScope(layer))

        if not exp.prepare(exp_context):
            raise GeoAlgorithmExecutionException(
                self.tr('Evaluation error: %s' % exp.evalErrorString()))

        selected = set(layer.selectedFeaturesIds())
        total = 100.0 / layer.featureCount()

        layer.startEditing()

        for current, feature in enumerate(layer.getFeatures()):

            if len(selected) == 0 or feature.id() in selected:

                rownum = current + 1
                exp_context.setFeature(feature)
                exp_context.lastScope().setVariable("row_number", rownum)
                value = exp.evaluate(exp_context)

                if exp.hasEvalError():

                    error = exp.evalErrorString()

                    raise GeoAlgorithmExecutionException(
                        self.tr('An error occurred while evaluating the calculation '
                            'string:\n%s' % error))

                else:

                    layer.changeAttributeValue(feature.id(), target_field_idx, value)

            progress.setPercentage(int(current * total))

        layer.commitChanges()

        # Redirect Input to Output
        self.setOutputValue(self.OUTPUT, self.getParameterValue(self.INPUT))