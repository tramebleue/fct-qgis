# -*- coding: utf-8 -*-

"""
MonotonicZ

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import numpy as np

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsGeometry,
    QgsLineString,
    # QgsMultiLineString,
    QgsProcessing,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingParameterNumber,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class MonotonicZ(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Adjust Z values for each vertex,
    so that Z always decreases from upstream to downstream.

    Input linestrings must be properly oriented from upstream to downstream,
    and should be aggregated by Hack order.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'MonotonicZ')

    NODATA = 'NODATA'
    MIN_Z_DELTA = 'MIN_Z_DELTA'
    SMOOTH_WINDOW = 'SMOOTH_WINDOW'
    NOISE_POWER = 'NOISE_POWER'

    def initParameters(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterNumber(
            self.NODATA,
            self.tr('No-Data Value'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=-99999))

        self.addParameter(QgsProcessingParameterNumber(
            self.MIN_Z_DELTA,
            self.tr('Minimum Z Delta'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=.0001))

        self.addParameter(QgsProcessingParameterNumber(
            self.SMOOTH_WINDOW,
            self.tr('Smooth Window'),
            type=QgsProcessingParameterNumber.Integer,
            defaultValue=20))

        self.addParameter(QgsProcessingParameterNumber(
            self.NOISE_POWER,
            self.tr('Noise Power'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=1.0))

    def inputLayerTypes(self): #pylint: disable=no-self-use,missing-docstring
        return [QgsProcessing.TypeVectorLine]

    def outputName(self): #pylint: disable=missing-docstring
        return self.tr('Adjusted Z Profile')

    def outputWkbType(self, inputWkbType): #pylint: disable=no-self-use,missing-docstring
        return inputWkbType

    def supportInPlaceEdit(self, layer): #pylint: disable=unused-argument,no-self-use,missing-docstring
        return True

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            import scipy.signal
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: scipy.signal')

    def prepareAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, 'INPUT', context)

        if not QgsWkbTypes.hasZ(layer.wkbType()):
            feedback.reportError(self.tr('Input must have Z coordinate.'), True)
            return False

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Multipart geometries are not currently supported'), True)
            return False

        self.nodata = self.parameterAsDouble(parameters, self.NODATA, context) or None
        self.z_delta = self.parameterAsDouble(parameters, self.MIN_Z_DELTA, context)
        self.smooth_window = self.parameterAsInt(parameters, self.SMOOTH_WINDOW, context)
        self.noise_power = self.parameterAsDouble(parameters, self.NOISE_POWER, context) or None

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        from scipy import signal

        z_delta = self.z_delta
        smooth_window = self.smooth_window
        noise_power = self.noise_power
        nodata = self.nodata

        def transform(geometry):
            """
            Adjust Z so that it decreases downward,
            and slope is always positive.
            """

            z = np.array([v.z() for v in geometry.vertices()])
            skip = (z == nodata)

            if z.shape[0] == 0:
                return geometry

            if smooth_window > 0:
                z = signal.wiener(z, smooth_window, noise_power)

            adjusted = np.full_like(z, nodata)
            zmax = float('inf')

            for i in range(z.shape[0]):

                if skip[i]:
                    continue

                if z[i] > zmax:

                    adjusted[i] = zmax
                    zmax = zmax - z_delta

                else:

                    zmax = adjusted[i] = z[i]

            points = list()

            for i, vertex in enumerate(geometry.vertices()):
                vertex.setZ(float(adjusted[i]))
                points.append(vertex)

            return QgsLineString(points)

        geometry = feature.geometry()

        # if geometry.isMultipart():

        #     parts = QgsMultiLineString()

        #     for part in geometry.asGeometryCollection():
        #         linestring = transform(part)
        #         parts.addGeometry(linestring)

        #     feature.setGeometry(QgsGeometry(parts))

        # else:

        feature.setGeometry(QgsGeometry(transform(geometry)))

        return [feature]
