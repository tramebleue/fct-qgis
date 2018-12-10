# -*- coding: utf-8 -*-

from qgis.PyQt.QtCore import (
    QCoreApplication,
    QVariant
)

from qgis.core import (
    QgsApplication,
    QgsGeometry,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsWkbTypes
)

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

        extent: QgsRectangle
            Rectangle to draw sample from

        radius: float
            Minimum distance between two samples

        k: integer
            Maximum number of samples to generate before rejection (see Bridson, 2007)

        existing_samples: list-of-QgsPointXY
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
        """ Emit a new sample, and return the corresponding QgsPointXY

        Parameters
        ----------

        point: QgsPointXY
            location of the sample to emit
        """

        i = len(self.samples)
        feature = QgsFeature()
        feature.setId(i)
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        self.index.insertFeature(feature)

        self.samples.append(point)
        self.active_list.append(point)
        
        return point

    def nearest_distance(self, point):
        """ Square distance to nearest emitted sample

        Parameters
        ----------

        point: QgsPointXY
        """

        for i in self.index.nearestNeighbor(point, 1):

            p = self.samples[i]
            return point.distance(p)

        return float('inf')

    def accept(self, point):
        """ Test if given location matches acceptance criteria :
        it must be within the sampled extent
        and no too close to existing samples.

        Parameters
        ----------

        point: QgsPointXY,
            candidate location
        """

        return self.extent.contains(point) and self.nearest_distance(point) > self.radius

    def __next__(self):
        """ Emit a new random sample,
            or return None if no new sample could be generated.
        """

        if not self.samples:

            # pick random point inside domain
            
            while True:

                x = self.extent.xMinimum() + np.random.uniform() * self.extent.width()
                y = self.extent.yMinimum() + np.random.uniform() * self.extent.height()
                p = QgsPointXY(x, y)
                
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

                p = QgsPointXY(x, y)

                if self.accept(p):
                    
                    return self.sample(p)

            # Reject sample i after k tries

            if i < len(self.active_list) - 1:
                self.active_list[i] = self.active_list.pop()
            else:
                self.active_list.pop()

        raise StopIteration

    def __iter__(self):
        """ Emits a valid serie of random samples.
        """

        return self


class RandomPoissonDiscSampling(QgsProcessingFeatureBasedAlgorithm):

    PK_FIELD = 'PK_FIELD'
    EXISTING_SAMPLES = 'EXISTING_SAMPLES'
    DISTANCE = 'DISTANCE'
    REJECTION_LIMIT = 'REJECTION_LIMIT'

    def tags(self):
        return self.tr('random,sampling,dither').split(',')

    def group(self):
        return self.tr('Tools for Vectors')

    def groupId(self):
        return 'fctvectortools'

    def name(self):
        return 'randompoissondiscsampling'

    def displayName(self):
        return self.tr('Random Poisson Disc Sampling')

    def inputLayerTypes(self):
        return [ QgsProcessing.TypeVectorPolygon ]

    def outputName(self):
        return self.tr('Poisson Disc Samples')

    def outputLayerType(self):
        return QgsProcessing.TypeVectorPoint

    def outputWkbType(self, inputWkbType):
        return QgsWkbTypes.Point

    # def icon(self):
    #     return QgsApplication.getThemeIcon("/algorithms/mAlgorithmSumPoints.svg")

    # def svgIconPath(self):
    #     return QgsApplication.iconPath("/algorithms/mAlgorithmSumPoints.svg")

    def tr(self, string, context=''):
        
        if context == '':
            context = 'FluvialCorridorToolbox'

        return QCoreApplication.translate(context, string)

    def __init__(self):

        super().__init__()
        
        self.pk_field = None
        self.distance = 50.0
        self.k = 30
        self.fid = 0

        self.R2 = np.square(self.distance)
        self.global_index = None
        self.global_samples = None
        self.sample_index = None

    def initParameters(self, config=None):

        self.addParameter(QgsProcessingParameterVectorLayer(self.EXISTING_SAMPLES,
                                                            self.tr('Existing Samples'),
                                                            [ QgsProcessing.TypeVectorPoint ],
                                                            optional=True))

        self.addParameter(QgsProcessingParameterField(self.PK_FIELD,
                                                      self.tr('Primary Key Field'),
                                                      parentLayerParameterName='INPUT',
                                                      type=QgsProcessingParameterField.Numeric))

        self.addParameter(QgsProcessingParameterDistance(self.DISTANCE,
                                                         self.tr('Minimum Distance between Samples'),
                                                         defaultValue=50.0))

        self.addParameter(QgsProcessingParameterNumber(self.REJECTION_LIMIT,
                                                       self.tr('Rejection Limit'),
                                                       type=QgsProcessingParameterNumber.Integer,
                                                       minValue=1,
                                                       defaultValue=30))

    def prepareAlgorithm(self, parameters, context, feedback):

        self.distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        self.R2 = np.square(self.distance)
        self.global_index = QgsSpatialIndex()
        self.global_samples = list()
        self.k = self.parameterAsInt(parameters, self.REJECTION_LIMIT, context)
        self.pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        self.fid = 0

        samples = self.parameterAsVectorLayer(parameters, self.EXISTING_SAMPLES, context)

        if samples is None:

            self.sample_index = None

        else:

            self.samples = samples
            self.sample_index = QgsSpatialIndex(samples.getFeatures())

        return True

    def outputFields(self, inputFields):

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

    def samples_by_polygon(self, polygon):

        selection = list()

        if self.sample_index is None:

            return selection

        for sample_id in sample_index.intersects(polygon.boundingBox()):

            sample = samples.getFeatures(QgsFeatureRequest(sample_id)).next()

            if polygon.contains(sample.geometry()):
                selection.append(sample.geometry().asPoint())

        return selection

    def nearest_distance(self, sample):

            for neighid in self.global_index.nearestNeighbor(sample, 1):
                neigh = self.global_samples[neighid]
                return sample.distance(neigh)

            return float('inf')

    def processFeature(self, feature, context, feedback):

        pk = feature.attribute(self.pk_field)

        polygon = feature.geometry()
        existing_samples = self.samples_by_polygon(polygon)
        sampler = PoissonDiscSampler(polygon.boundingBox(), self.distance, self.k, existing_samples)
        out_features = list()

        for sample in chain(existing_samples, sampler):

            if polygon.contains(sample) and self.nearest_distance(sample) > self.distance:

                out_feature = QgsFeature()
                out_feature.setAttributes([
                        self.fid,
                        sample.x(),
                        sample.y(),
                        pk
                    ])
                out_feature.setGeometry(QgsGeometry.fromPointXY(sample))
                out_feature.setId(self.fid)
                
                self.global_index.insertFeature(out_feature)
                self.global_samples.append(sample)
                self.fid = self.fid + 1

                out_features.append(out_feature)

        return out_features

    def createInstance(self):

        return type(self)()


