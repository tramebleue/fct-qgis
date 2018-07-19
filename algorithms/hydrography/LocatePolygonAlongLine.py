# -*- coding: utf-8 -*-

"""
***************************************************************************
    MeasureDGO.py
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
__date__ = 'June 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper

from collections import defaultdict, namedtuple
from math import sqrt
import numpy as np

Segment = namedtuple('Segment', [ 'meas', 'axis', 'geometry' ])

class LocatePolygonAlongLine(GeoAlgorithm):

    INPUT_LAYER = 'INPUT'
    INPUT_LINES = 'LINES'
    OUTPUT_LAYER = 'OUTPUT'
    # DGO_PK_FIELD = 'DGO_PK'
    AXIS_FIELD = 'AXIS'
    MEASURE_FIELD = 'MEASURE'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Locate Polygon Along Line')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Polygons'),
                                          [ParameterVector.VECTOR_TYPE_POLYGON]))

        # self.addParameter(ParameterTableField(self.DGO_PK_FIELD,
        #                                       self.tr('Polygon Primary Key'),
        #                                       parent=self.INPUT_LAYER,
        #                                       datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.INPUT_LINES,
                                          self.tr('Reference Lines'),
                                          [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterTableField(self.AXIS_FIELD,
                                              self.tr('Axis Field'),
                                              parent=self.INPUT_LINES,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER,
                                              optional=False))

        self.addParameter(ParameterTableField(self.MEASURE_FIELD,
                                              self.tr('Measure Field'),
                                              parent=self.INPUT_LINES,
                                              datatype=ParameterTableField.DATA_TYPE_NUMBER,
                                              optional=False))

        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Polygon Linear Location')))

    def processAlgorithm(self, progress):

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LAYER))
        lines = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LINES))
        axis_field = self.getParameterValue(self.AXIS_FIELD)
        meas_field = self.getParameterValue(self.MEASURE_FIELD)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                layer,
                vector_helper.resolveField(lines, axis_field),
            ),
            QGis.WKBPoint,
            layer.crs())

        # Step 1

        progress.setText(self.tr('Intersect polygons with lines'))

        lines_index = QgsSpatialIndex(lines.getFeatures())

        features = vector.features(layer)
        total = 100.0 / len(features)
        # { Polygon PK: list of ( polygon id(), line id(), intersection ) }
        index = defaultdict(list)
        errors = 0

        def processGeometry(geometry, feature, intersector):

            fid = feature.id()
            meas = intersector[meas_field]
            axis = intersector[axis_field]

            if geometry.type() == QGis.Line:

                if geometry.isMultipart():

                    for part in geometry.asMultiPolyline():

                        geom = QgsGeometry.fromPolyline(part)
                        segment = Segment(meas, axis, geom)
                        index[fid].append(segment)

                else:

                    segment = Segment(meas, axis, geometry)
                    index[fid].append(segment)

        for current, feature in enumerate(features):

            for intersector_fid in lines_index.intersects(feature.geometry().boundingBox()):

                intersector = lines.getFeatures(QgsFeatureRequest(intersector_fid)).next()

                try:

                    if intersector.geometry().intersects(feature.geometry()):

                        intersection = intersector.geometry().intersection(feature.geometry())

                        if QgsWKBTypes.flatType(intersection.geometry().wkbType()) == QgsWKBTypes.GeometryCollection:

                            for geometry in intersection.asGeometryCollection():

                               processGeometry(geometry, feature, intersector)

                        else:

                            processGeometry(intersection, feature, intersector)

                except:
                    
                    errors = errors + 1

                progress.setPercentage(int(current * total))

        ProcessingLog.addToLog(
                            ProcessingLog.LOG_INFO,
                            "%d intersection errors" % errors)

        # Step 2

        progress.setText(self.tr('Locate Object on Linear Reference'))
        total = 100.0 / len(index.keys())
        progress.setPercentage(0)

        for current, fid in enumerate(index.keys()):

            segments = list()
            axis = None

            for segment in index[fid]:

                segments.append(segment)

                if axis is None or segment.axis < axis:
                    axis = segment.axis

            def by_meas_desc(a, b):
                
                if a.meas == b.meas:
                    return 0
                elif a.meas < b.meas:
                    return 1
                else:
                    return -1

            segments = filter(lambda f: f.axis == axis, segments)
            segments.sort(by_meas_desc)
            length = np.sum([ segment.geometry.length() for segment in segments ])

            # Find first segment after the "middle" of the intersection
            # between polygon and lines.
            # s is the linear coordinate of start point of segment i
            i = 0
            s = 0.0

            while (s + segments[i].geometry.length()) < 0.5*length:
                s = s + segments[i].geometry.length()
                i = i + 1

            p = segments[i].geometry.interpolate(0.5*length - s)

            feature = layer.getFeatures(QgsFeatureRequest(fid)).next()

            outfeature = QgsFeature()
            outfeature.setGeometry(p)
            outfeature.setAttributes(
                feature.attributes() + [
                    axis
                ])
            writer.addFeature(outfeature)

            progress.setPercentage(int(current * total))
