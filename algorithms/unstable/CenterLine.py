# -*- coding: utf-8 -*-

"""
***************************************************************************
    CenterLine.py
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

from PyQt4.QtCore import QSettings
from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint
from qgis.core import QgsFeatureRequest, QgsExpression, QgsVectorFileWriter
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.tools.system import getTempFilenameInTempFolder
from processing.core.Processing import Processing
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults

class CenterLine(GeoAlgorithm):

    INPUT_POLYLINES = 'INPUT_POLYLINES'
    INPUT_POLYGONS = 'INPUT_POLYGONS'
    DISAGGREGATION_STEP = 'DISAGGREGATION_STEP'
    OUTPUT = 'OUTPUT'

    STEPS = 17

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Center Line')
        self.group, self.i18n_group = self.trAlgorithm('Unstable')

        self.addParameter(ParameterVector(self.INPUT_POLYLINES,
                                          self.tr('Input lines'), [ParameterVector.VECTOR_TYPE_LINE]))
        self.addParameter(ParameterVector(self.INPUT_POLYGONS,
                                          self.tr('Input polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterNumber(self.DISAGGREGATION_STEP,
                                          self.tr('Disaggregation step'), default=50, minValue=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Center line')))

    def nextStep(self, description, progress):
        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, description)
        progress.setText(description)
        progress.setPercentage(int(100.0 * self.current_step / self.STEPS))
        self.current_step += 1


    def processAlgorithm(self, progress):

        SIMPLIFY_TOLERANCE = 5
        SMOOTH_ITERATIONS = 4
        SMOOTH_OFFSET = .4
        
        disaggregation_step = self.getParameterValue(self.DISAGGREGATION_STEP)
        self.current_step = 0

        display_result = True
        def handleResult(description):
            def _handle(alg, *args, **kw):
                if display_result:
                    for out in alg.outputs:
                        out.description = description
                    handleAlgorithmResults(alg, *args, **kw)
            return _handle

        # Prepare inputs
        
        self.nextStep('Extract polyline end points ...', progress)
        ExtremePoints = Processing.runAlgorithm('fluvialtoolbox:extremepoints', None,
                            {
                                'INPUT': self.getParameterValue(self.INPUT_POLYLINES)
                            })

        self.nextStep('Simplify polygons ...', progress)
        SimplifiedPolygons = Processing.runAlgorithm('qgis:simplifygeometries', handleResult('SimplifiedPolygons'),
                            {
                              'INPUT': self.getParameterValue(self.INPUT_POLYGONS),
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })

        self.nextStep('Convert polylines to polygons ...', progress)
        PolyToLine = Processing.runAlgorithm('qgis:polygonstolines', None,
                            {
                                'INPUT': SimplifiedPolygons.getOutputValue('OUTPUT')
                            })

        # Split lines in PolyToLine w.r.t DISAGGREGATION_STEP
        
        self.nextStep('Split lines w/ disaggregation step ...', progress)
        SplittedPolyToLine = Processing.runAlgorithm('fluvialtoolbox:splitlines', None,
                            {
                              'INPUT': PolyToLine.getOutputValue('OUTPUT'),
                              'MAXLENGTH': disaggregation_step
                            })

        # Split PolyToLine with ExtremePoints
        # Number lines (UGO_ID) in PolyToLine

        self.nextStep('Find nearest objects ...', progress)
        NearTable = Processing.runAlgorithm('fluvialtoolbox:neartable', None,
                            {
                                'FROM': ExtremePoints.getOutputValue('OUTPUT'),
                                'FROM_ID_FIELD': 'FID',
                                'TO': PolyToLine.getOutputValue('OUTPUT'),
                                'TO_ID_FIELD': 'GID',
                                'NEIGHBORS': 1,
                                'SEARCH_DISTANCE': 0
                            })

        self.nextStep('Split lines at extreme points ...', progress)
        UGO = Processing.runAlgorithm('fluvialtoolbox:splitlineatnearestpoint', None,
                            {
                              'INPUT': SplittedPolyToLine.getOutputValue('OUTPUT'),
                              'NEAR_TABLE': NearTable.getOutputValue('OUTPUT')
                            })

        # Extract Points

        self.nextStep('Extract UGO points ...', progress)
        UGOPoints = Processing.runAlgorithm('qgis:extractnodes', None,
                            {
                                'INPUT': UGO.getOutputValue('OUTPUT')
                            })

        # Compute Thiessen polygons

        self.nextStep('Compute UGO Thiessen polygons ...', progress)
        UGOThiessenPolygons = Processing.runAlgorithm('qgis:voronoipolygons', handleResult('UGOThiessenPolygons'),
                            {
                              'INPUT': UGOPoints.getOutputValue('OUTPUT'),
                              'BUFFER': 5.0
                            })

        # Dissolve (merge) by UGO_ID

        self.nextStep('Aggregate UGO by ID ...', progress)
        AggregatedGO = Processing.runAlgorithm('saga:polygondissolvebyattribute', None,
                            {
                                'POLYGONS': UGOThiessenPolygons.getOutputValue('OUTPUT'),
                                'FIELD_1': 'GID',
                                'FIELD_2': 'UGO_ID',
                                'BND_KEEP': False
                            })

        # Intersect with INPUT_POLYGONS

        self.nextStep('Clip AGO to input polygons ...', progress)
        ClippedAGO = Processing.runAlgorithm('saga:intersect', None,
                            {
                                'A': AggregatedGO.getOutputValue('DISSOLVED'),
                                'B': SimplifiedPolygons.getOutputValue('OUTPUT'),
                                'SPLIT': True
                            })

        # Convert to linestring

        self.nextStep('Convert AGO to lines ...', progress)
        ClippedAGOLines = Processing.runAlgorithm('qgis:polygonstolines', None,
                            {
                                'INPUT': ClippedAGO.getOutputValue('RESULT')
                            })

        # Keep interior linestrings
        # Delete identical linestrings

        self.nextStep('Self intersect AGO lines ...', progress)
        SelfIntersectAGO = Processing.runAlgorithm('qgis:intersection', None,
                            {
                                'INPUT': ClippedAGOLines.getOutputValue('OUTPUT'),
                                'INPUT2': ClippedAGOLines.getOutputValue('OUTPUT')
                            })

        # Extract UGO boundaries (ie. lines that belong to two different UGO)

        self.nextStep('Extract center line ...', progress)
        extraction = self.exportFeaturesByExpression(
                    SelfIntersectAGO.getOutputValue('OUTPUT'),
                    'UGO_ID != ugo_id_2',
                    'centerline.shp')

        # Remove duplicates objects

        self.nextStep('Remove duplicate objects ...', progress)
        DeduplicatedLines = Processing.runAlgorithm('qgis:deleteduplicategeometries', None,
                            {
                                'INPUT': extraction
                            })

        # Simplify and smooth result

        self.nextStep('Simplify result ...', progress)
        SimplifiedCenterLine = Processing.runAlgorithm('qgis:simplifygeometries', None,
                            {
                              'INPUT': DeduplicatedLines.getOutputValue('OUTPUT'),
                              'TOLERANCE': SIMPLIFY_TOLERANCE
                            })

        self.nextStep('Smooth center line ...', progress)
        Processing.runAlgorithm('qgis:smoothgeometry', None,
                                {
                                  'INPUT_LAYER': SimplifiedCenterLine.getOutputValue('OUTPUT'),
                                  'OUTPUT_LAYER': self.getOutputValue(self.OUTPUT),
                                  'ITERATIONS': SMOOTH_ITERATIONS,
                                  'OFFSET': SMOOTH_OFFSET
                                })

        self.nextStep('Done !', progress)

    def exportFeaturesByExpression(self, inputURI, expression, basename):
        output = getTempFilenameInTempFolder(basename)
        layer = dataobjects.getObjectFromUri(inputURI)
        settings = QSettings()
        systemEncoding = settings.value('/UI/encoding', 'System')
        writer = QgsVectorFileWriter(output, systemEncoding,
                                     layer.pendingFields(),
                                     layer.dataProvider().geometryType(), layer.crs())
        query = QgsFeatureRequest(QgsExpression(expression))
        for feature in layer.getFeatures(query):
            newFeature = QgsFeature()
            newFeature.setAttributes(feature.attributes())
            newFeature.setGeometry(QgsGeometry(feature.geometry()))
            writer.addFeature(newFeature)
        del writer
        return output
