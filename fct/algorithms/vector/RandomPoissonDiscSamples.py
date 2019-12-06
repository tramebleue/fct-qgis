# -*- coding: utf-8 -*-

"""
Random Poisson Disc Samples

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import math
import numpy as np

from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QVariant
)

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsGeometry,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterDistance,
    QgsProcessingParameterNumber,
    QgsProcessingParameterField,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

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

    def __init__(self, extent, radius, k):
        """
        Parameters
        ----------

        extent: QgsRectangle
            Rectangle to draw sample from

        radius: float
            Minimum distance between two samples

        k: integer
            Maximum number of samples to generate before rejection (see Bridson, 2007)
        """

        self.samples = list()
        self.index = QgsSpatialIndex()

        self.extent = extent
        self.radius = radius
        self.k = k
        self.sq_radius = np.square(radius)

        self.cell_size = radius * math.sqrt(0.5)
        self.grid_width = math.ceil(extent.width() / self.cell_size)
        self.grid_height = math.ceil(extent.height() / self.cell_size)

        self.grid = np.zeros((self.grid_height, self.grid_width), dtype=np.int32)
        self.points = list()
        self.queue = list()

    def withinExtent(self, p):
        """
        p: QgsPointXY
        """
        return self.extent.contains(p)

    def generateAround(self, p):
        """
        p: QgsPointXY
        """

        theta = 2 * math.pi * np.random.uniform()
        radius = np.sqrt(3 * np.random.uniform() * self.sq_radius + self.sq_radius) # http://stackoverflow.com/a/9048443/64009
        x = p.x() + radius * math.cos(theta)
        y = p.y() + radius * math.sin(theta)

        return QgsPointXY(x, y)

    def near(self, p):
        """
        p: QgsPointXY
        """

        n = 2
        x = math.floor((p.x() - self.extent.xMinimum()) / self.cell_size)
        y = math.floor((p.y() - self.extent.yMinimum()) / self.cell_size)
        x0 = max(x - n, 0)
        y0 = max(y - n, 0)
        x1 = min(x + n + 1, self.grid_width)
        y1 = min(y + n + 1, self.grid_height)

        for y in range(y0, y1):
            for x in range(x0, x1):

                g = self.grid[y, x]

                if g > 0:

                    g = self.points[g]

                    if g.sqrDist(p) < self.sq_radius:
                        return True

        return False

    def accept(self, p):
        """
        p: QgsPointXY
        """

        self.queue.append(p)
        self.points.append(p)
        px = math.floor((p.x() - self.extent.xMinimum()) / self.cell_size)
        py = math.floor((p.y() - self.extent.yMinimum()) / self.cell_size)
        self.grid[py, px] = len(self.points) - 1

    def __iter__(self):
        """
        Return next point
        """

        while True:

            if not self.points:

                x = self.extent.xMinimum() + 0.5*np.random.uniform()*self.extent.width()
                y = self.extent.yMinimum() + 0.5*np.random.uniform()*self.extent.height()
                point = QgsPointXY(x, y)
                self.accept(point)
                yield point

            else:

                i = round(np.random.uniform() * (len(self.queue) - 1))
                point = self.queue[i]
                success = False

                for j in range(self.k):

                    q = self.generateAround(point)

                    if self.withinExtent(q) and not self.near(q):
                        self.accept(q)
                        success = True
                        yield q
                        break

                if not success:
                    
                    last = self.queue.pop()
                    if i < len(self.queue):
                        self.queue[i] = last

                if not self.queue:
                    break

class RandomPoissonDiscSamples(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """ Generate samples from a blue noise distribution,
        with a minimal distance between samples
    """

    METADATA = AlgorithmMetadata.read(__file__, 'RandomPoissonDiscSamples')

    PK_FIELD = 'PK_FIELD'
    DISTANCE = 'DISTANCE'
    REJECTION_LIMIT = 'REJECTION_LIMIT'

    #pylint: disable=missing-docstring,no-self-use,unused-argument

    def inputLayerTypes(self):
        return [QgsProcessing.TypeVectorPolygon]

    def outputName(self):
        return self.tr('Poisson Disc Samples')

    def outputLayerType(self):
        return QgsProcessing.TypeVectorPoint

    def outputWkbType(self, inputWkbType):
        return QgsWkbTypes.Point

    def initParameters(self, config=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Primary Key Field'),
            parentLayerParameterName='INPUT',
            type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterDistance(
            self.DISTANCE,
            self.tr('Minimum Distance between Samples'),
            parentParameterName='INPUT',
            defaultValue=50.0))

        self.addParameter(QgsProcessingParameterNumber(
            self.REJECTION_LIMIT,
            self.tr('Rejection Limit'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=30))

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        self.distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        self.k = self.parameterAsInt(parameters, self.REJECTION_LIMIT, context)
        self.pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        self.fid = 0

        return True

    def outputFields(self, inputFields): #pylint: disable=unused-argument,missing-docstring

        fields = QgsFields()

        for field in [
                QgsField('PID', QVariant.Int, len=10),
                QgsField('X', QVariant.Double, len=10, prec=2),
                QgsField('Y', QVariant.Double, len=10, prec=2)
            ]:

            fields.append(field)

        pkidx = inputFields.lookupField(self.pk_field)
        fields.append(inputFields.at(pkidx))

        return fields

    def processFeature(self, feature, context, feedback): #pylint: disable=unused-argument,missing-docstring

        pk = feature.attribute(self.pk_field)

        polygon = feature.geometry()
        extent = polygon.boundingBox()

        sampler = PoissonDiscSampler(extent, self.distance, self.k)
        out_features = list()

        estimated_count = extent.area() / (self.distance*self.distance)
        total = 100.0 / estimated_count if estimated_count else 0
        current = 0

        for sample in sampler:

            if feedback.isCanceled():
                break

            if polygon.contains(sample):

                out_feature = QgsFeature()
                out_feature.setAttributes([
                    self.fid,
                    sample.x(),
                    sample.y(),
                    pk
                ])
                out_feature.setGeometry(QgsGeometry.fromPointXY(sample))
                out_feature.setId(self.fid)

                self.fid += 1

                out_features.append(out_feature)

                feedback.setProgress(int(current * total))
                current += 1

        return out_features
