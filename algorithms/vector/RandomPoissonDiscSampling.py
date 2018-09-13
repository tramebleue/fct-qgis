# -*- coding: utf-8 -*-

"""
***************************************************************************
    RandomPoints.py
    ---------------------
    Date                 : February 2018
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

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

from ...core import vector as vector_helper

import numpy as np
import math
from itertools import chain

class PoissonDiscSampler(object):
    """ 2D Poisson Disc Sampler

        Generate samples from a blue noise distribution [4],
        ie. randomly but maintaining a minimal distance between samples.

    [1] Bridson (2007). Fast Poisson disk sampling in arbitrary dimensions.
        http://dl.acm.org/citation.cfm?doid=1278780.1278807

    [2] Mike Bostock Poisson Disc explanation
        https://bl.ocks.org/mbostock/dbb02448b0f93e4c82c3

    [3] Javascript implementation and demo
        https://bl.ocks.org/mbostock/19168c663618b7f07158

    [4] Blue noise definition
        https://en.wikipedia.org/wiki/Colors_of_noise#Blue_noise

    """

    def __init__(self, extent, radius, k, existing_samples=None):
        """
        Parameters
        ----------

        extent : QgsRectangle
            Rectangle to draw sample from

        radius : float
            Minimum distance between two samples

        k : integer
            Maximum number of samples to generate before rejection (see Bridson, 2007)

        existing_samples: list-of-QgsPoint
            Initialize samples from this list of points
        """
        
        self.samples = list()
        self.index = QgsSpatialIndex()

        self.extent = extent
        self.radius = radius
        self.k = k
        self.R2 = np.square(radius)
        self.active_list = list()
        
        if existing_samples:
            for s in existing_samples:
                self.sample(s)

    def sample(self, point):
        """ Emit a new sample, and return the corresponding QgsPoint

        Parameters
        ----------

        point: QgsPoint
            location of the sample to emit
        """

        i = len(self.samples)
        feature = QgsFeature()
        feature.setFeatureId(i)
        feature.setGeometry(QgsGeometry.fromPoint(point))
        self.index.insertFeature(feature)

        self.samples.append(point)
        self.active_list.append(point)
        
        return point

    def sq_nearest_distance(self, point):
        """ Square distance to nearest emitted sample

        Parameters
        ----------

        point: QgsPoint
        """

        for i in self.index.nearestNeighbor(point, 1):

            p = self.samples[i]
            return point.sqrDist(p)

        return float('inf')

    def accept(self, point):
        """ Test if given location matches acceptance criteria :
        it must be within the sampled extent
        and no too close to existing samples.

        Parameters
        ----------

        point: QgsPoint,
            candidate location
        """

        return self.extent.contains(point) and self.sq_nearest_distance(point) > self.R2

    def next(self):
        """ Emit a new random sample,
            or return None if no new sample could be generated.
        """

        if not self.samples:

            # pick random point inside domain
            
            while True:

                x = self.extent.xMinimum() + np.random.uniform() * self.extent.width()
                y = self.extent.yMinimum() + np.random.uniform() * self.extent.height()
                p = QgsPoint(x, y)
                
                if self.accept(p):

                    return self.sample(p)

        while self.active_list:

            i = int(np.floor(np.random.uniform() * len(self.active_list)))
            active_sample = self.active_list[i]

            for j in range(self.k):

                a = 2 * math.pi * np.random.uniform()
                r = np.sqrt(self.R2 * (1 + 3 * np.random.uniform()))
                x = active_sample.x() + r * math.cos(a)
                y = active_sample.y() + r * math.sin(a)

                p = QgsPoint(x, y)

                if self.accept(p):
                    
                    return self.sample(p)

            # Reject sample i after k tries

            if i < len(self.active_list) - 1:
                self.active_list[i] = self.active_list.pop()
            else:
                self.active_list.pop()

        return None

    def __iter__(self):
        """ Emits a valid serie of random samples.
        """

        while True:

            next_sample = next(self)
            if next_sample is None:
                break

            yield next_sample


class RandomPoissonDiscSampling(GeoAlgorithm):

    INPUT = 'INPUT'
    PK_FIELD = 'PK_FIELD'
    EXISTING_SAMPLES = 'EXISTING_SAMPLES'
    DISTANCE = 'DISTANCE'
    REJECTION_LIMIT = 'REJECTION_LIMIT'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Random Poisson Disc Sampling')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Vectors')

        self.addParameter(ParameterVector(self.INPUT,
                                          self.tr('Input Polygons'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        
        self.addParameter(ParameterTableField(self.PK_FIELD,
                                          self.tr('Primary Key Field'),
                                          parent=self.INPUT,
                                          datatype=ParameterTableField.DATA_TYPE_NUMBER))

        self.addParameter(ParameterVector(self.EXISTING_SAMPLES,
                                          self.tr('Existing Samples'), [ParameterVector.VECTOR_TYPE_POINT],
                                          optional=True))

        self.addParameter(ParameterNumber(self.DISTANCE,
                                          self.tr('Minimum Distance between Samples'),
                                          minValue=0.0, default=50.0))

        self.addParameter(ParameterNumber(self.REJECTION_LIMIT,
                                          self.tr('Rejection Limit'),
                                          minValue=1, default=30))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Poisson Disc Samples')))


    def processAlgorithm(self, progress):

        layer = processing.getObject(self.getParameterValue(self.INPUT))
        samples = processing.getObject(self.getParameterValue(self.EXISTING_SAMPLES))
        pk_field = self.getParameterValue(self.PK_FIELD)
        distance = self.getParameterValue(self.DISTANCE)
        k = self.getParameterValue(self.REJECTION_LIMIT)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            [
                QgsField('PID', QVariant.Int, len=10),
                QgsField('X', QVariant.Double, len=10, prec=2),
                QgsField('Y', QVariant.Double, len=10, prec=2),
                vector_helper.resolveField(layer, pk_field)
            ],
            QGis.WKBPoint,
            layer.crs())

        if samples is None:

            def samples_by_polygon(polygon):
                
                return list()

        else:

            sample_index = QgsSpatialIndex(samples.getFeatures())

            def samples_by_polygon(polygon):

                selection = list()

                for sample_id in sample_index.intersects(polygon.boundingBox()):

                    sample = samples.getFeatures(QgsFeatureRequest(sample_id)).next()

                    if polygon.contains(sample.geometry()):
                        selection.append(sample.geometry().asPoint())

                return selection

        features = vector.features(layer)
        total = 100.0 / len(features)
        fid = 0

        # Maintain a global list of generated samples
        # in order to avoid boundary effects between input polygons
        R2 = np.square(distance)
        global_index = QgsSpatialIndex()
        global_samples = list()

        def sq_nearest_distance(sample):

            for neighid in global_index.nearestNeighbor(sample, 1):
                neigh = global_samples[neighid]
                return sample.sqrDist(neigh)

            return float('inf')

        for current, feature in enumerate(features):

            pk = feature.attribute(pk_field)

            polygon = feature.geometry()
            existing_samples = samples_by_polygon(polygon)
            sampler = PoissonDiscSampler(polygon.boundingBox(), distance, k, existing_samples)

            for sample in chain(existing_samples, sampler):

                if polygon.contains(sample) and sq_nearest_distance(sample) > R2:

                    out_feature = QgsFeature()
                    out_feature.setAttributes([
                            fid,
                            sample.x(),
                            sample.y(),
                            pk
                        ])
                    out_feature.setGeometry(QgsGeometry.fromPoint(sample))
                    writer.addFeature(out_feature)

                    out_feature.setFeatureId(fid)
                    global_index.insertFeature(out_feature)
                    global_samples.append(sample)
                    fid = fid + 1

            progress.setPercentage(int(current * total))


