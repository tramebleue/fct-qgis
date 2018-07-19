# -*- coding: utf-8 -*-

"""
***************************************************************************
    Sequencing2.py
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

from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsSpatialIndex, QgsFeatureRequest, QgsFields, QgsField
from qgis.core import QgsVectorLayer
from qgis.core import NULL
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from ...core import vector as vector_helper

from collections import defaultdict

def backtrack_sequence(n, t, backtracks):

    stack = [ t ]
    segments = list()
    passed_through = set()
    found = False

    while stack:

        na = stack.pop()

        for segment, nb in backtracks[na]:

            if segment in passed_through:
                continue
            
            segments.append(segment)
            passed_through.add(segment)
            
            if nb != n:
                stack.append(nb)
            else:
                found = True

    if found:
        return segments
    else:
        return list()


class MatchNetworkSegments(GeoAlgorithm):

    NETWORK1 = 'NETWORK1'
    NETWORK2 = 'NETWORK2'
    NETWORK2_PK_FIELD = 'NETWORK2_PK_FIELD'
    PAIRS = 'PAIRS'
    NETWORK1_PAIR_FIELD = 'NETWORK1_PAIR_FIELD'
    NETWORK2_PAIR_FIELD = 'NETWORK2_PAIR_FIELD'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Match Network Segments')
        self.group, self.i18n_group = self.trAlgorithm('Hydrography')

        self.addParameter(ParameterVector(self.NETWORK1,
                                          self.tr('Input Network Layer'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterVector(self.NETWORK2,
                                          self.tr('Paired Network Layer'), [ParameterVector.VECTOR_TYPE_LINE]))
        
        self.addParameter(ParameterTableField(self.NETWORK2_PK_FIELD,
                                          self.tr('Paired Layer Primary Key'),
                                          parent=self.NETWORK2,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.PAIRS,
                                          self.tr('Input to Paired Node Pairs'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterTableField(self.NETWORK1_PAIR_FIELD,
                                          self.tr('Network 1 Pair Field'),
                                          parent=self.PAIRS,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterTableField(self.NETWORK2_PAIR_FIELD,
                                          self.tr('Network 2 Pair Field'),
                                          parent=self.PAIRS,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))
        
        self.addOutput(OutputVector(self.OUTPUT, self.tr('Matched Segments')))

    def processAlgorithm(self, progress):

        network1 = dataobjects.getObjectFromUri(self.getParameterValue(self.NETWORK1))
        network2 = dataobjects.getObjectFromUri(self.getParameterValue(self.NETWORK2))
        pair_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.PAIRS))
        network2_pk_field = self.getParameterValue(self.NETWORK2_PK_FIELD)
        network1_pair_field = self.getParameterValue(self.NETWORK1_PAIR_FIELD)
        network2_pair_field = self.getParameterValue(self.NETWORK2_PAIR_FIELD)

        # TODO check input structure
        
        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                network1,
                vector_helper.resolveField(network2, network2_pk_field),
                QgsField('MATCHDIST', QVariant.Double, len=10, prec=2)
            ),
            network1.dataProvider().geometryType(),
            network1.crs())
        
        # forwardtracks1 = { nb: list(segment, na) }
        forwardtracks1 = defaultdict(list)
        # backtracks2 = { na: list(segment, nb) }
        backtracks2 = defaultdict(list)
        # pairs = { n1: n2 }
        pairs = dict()

        stack = list()
        seen_segments = set()

        progress.setText(self.tr('Build Network1 Index ...'))
        total = 100.0 / network1.featureCount()
        for current, edge in enumerate(network1.getFeatures()):

            a = edge.attribute('NODE_A')
            b = edge.attribute('NODE_B')

            forwardtracks1[b].append((edge.id(), a))

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Build Network2 Index ...'))
        total = 100.0 / network2.featureCount()
        for current, edge in enumerate(network2.getFeatures()):

            a = edge.attribute('NODE_A')
            b = edge.attribute('NODE_B')

            backtracks2[a].append((edge.id(), b))

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Build Pair Index ...'))
        total = 100.0 / pair_layer.featureCount()
        for current, pair in enumerate(pair_layer.getFeatures()):

            n1 = pair.attribute(network1_pair_field)
            n2 = pair.attribute(network2_pair_field)

            if n2 is None or n2 == NULL:
                continue

            pairs[n1] = n2

            if pair.attribute('TYPE') == 'EXUT':
                stack.append(n1)

            progress.setPercentage(int(current * total))

        def match_segments(seq1, seq2):

            target_segments = [ network2.getFeatures(QgsFeatureRequest(fid)).next() for fid in seq2 ]

            for fid in seq1:

                if fid in seen_segments:
                    # segment has already been output
                    continue

                segment = network1.getFeatures(QgsFeatureRequest(fid)).next()
                midpoint = segment.geometry().interpolate(0.5 * segment.geometry().length())
                distance = float('inf')
                paired = None

                for target_segment in target_segments:

                    d = midpoint.distance(target_segment.geometry())
                    if d < distance:
                        distance = d
                        paired = target_segment

                if paired:

                    out_feature = QgsFeature()
                    out_feature.setGeometry(segment.geometry())
                    out_feature.setAttributes(segment.attributes() + [
                            paired.attribute(network2_pk_field),
                            distance
                        ])
                    writer.addFeature(out_feature)

                    seen_segments.add(fid)

                # else:

                #     out_feature = QgsFeature()
                #     out_feature.setGeometry(segment.geometry())
                #     out_feature.setAttributes(segment.attributes() + [
                #             None,
                #             None
                #         ])
                #     writer.addFeature(out_feature)

        progress.setText(self.tr('Match segments ...'))
        total = 100.0 / len(pairs)
        current = 0
        segments_with_errors = list()
        seen_nodes = set()

        while stack:

            n1 = stack.pop()
            current = current + 1
            progress.setPercentage(int(current * total))

            cursor1 = [ n1 ]
            backtracks1 = defaultdict(list)
            targets = list()
            passed_through = set()

            # if n1 == 234101:
            #     ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'N1 -> %s' % [ a for s, a in forwardtracks1[n1] ])

            while cursor1:

                nb = cursor1.pop()

                for segment, na in forwardtracks1[nb]:

                    # if segment in passed_through:
                    #     continue

                    backtracks1[na].append((segment, nb))
                    passed_through.add(segment)
                    
                    if pairs.has_key(na):
                        targets.append(na)
                    
                    elif na not in passed_through:
                        
                        cursor1.append(na)
                        passed_through.add(na)

            # if n1 == 234101:
            #    ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Targets -> %s' % targets)

            for t1 in targets:

                n2 = pairs[n1]
                t2 = pairs[t1]

                # if n1 == 234101:
                #     ProcessingLog.addToLog(ProcessingLog.LOG_INFO, '(%d, %d) -> (%d, %d)' % (n1,t1,n2,t2))
                #     ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Segments N1 = %s' % segments1)
                #     ProcessingLog.addToLog(ProcessingLog.LOG_INFO, 'Segments N2 = %s' % segments2)

                segments1 = backtrack_sequence(n1, t1, backtracks1)
                segments2 = backtrack_sequence(n2, t2, backtracks2)

                if segments2:
                    
                    match_segments(segments1, segments2)

                else:

                    # Empty segments2 :
                    # Impossible to backtrack from t2 to n2,
                    # whereas there is a path from t1 to n1 in input network
                    
                    ProcessingLog.addToLog(ProcessingLog.LOG_WARNING, 'Network Topology Error, Node Pair in Paired Network (%d, %d)' % (n2, t2))
                    segments_with_errors.extend(segments1)

                if t1 not in seen_nodes:
                    
                    stack.append(t1)
                    seen_nodes.add(t1)

        progress.setText(self.tr('Output unpaired segments ...'))
        total = 100.0 / network1.featureCount()

        for current, segment in enumerate(network1.getFeatures()):

            if segment.id() not in seen_segments:

                out_feature = QgsFeature()
                out_feature.setGeometry(segment.geometry())
                out_feature.setAttributes(segment.attributes() + [
                        None,
                        segment.geometry().length()
                    ])
                writer.addFeature(out_feature)

                seen_segments.add(segment.id())

            progress.setPercentage(int(current * total))

        progress.setText(self.tr('Select Possible Pairing Errors in Input Network  ...'))
        network1.setSelectedFeatures(segments_with_errors)