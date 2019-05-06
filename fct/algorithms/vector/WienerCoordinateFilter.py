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
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata

class WienerCoordinateFilter(AlgorithmMetadata, QgsProcessingFeatureBasedAlgorithm):
    """
    Smooth Z or M coordinate along linestring using a Wiener filter.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'WienerCoordinateFilter')

    COORDINATE = 'COORDINATE'
    NODATA = 'NODATA'
    SMOOTH_WINDOW = 'SMOOTH_WINDOW'
    NOISE_POWER = 'NOISE_POWER'

    Z_COORDINATE = 0
    M_COORDINATE = 1

    def initParameters(self, configuration=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterEnum(
            self.COORDINATE,
            self.tr('Coordinate To Filter'),
            options=['Z', 'M'],
            defaultValue=self.Z_COORDINATE))

        self.addParameter(QgsProcessingParameterNumber(
            self.NODATA,
            self.tr('No-Data Value'),
            type=QgsProcessingParameterNumber.Double,
            defaultValue=-99999))

        self.addParameter(QgsProcessingParameterNumber(
            self.SMOOTH_WINDOW,
            self.tr('Smooth Window'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=20))

        self.addParameter(QgsProcessingParameterNumber(
            self.NOISE_POWER,
            self.tr('Noise Power'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0,
            defaultValue=1.0,
            optional=True))

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
        coordinate = self.parameterAsInt(parameters, self.COORDINATE, context)

        if not coordinate in [self.Z_COORDINATE, self.M_COORDINATE]:
            feedback.reportError(self.tr('Invalide option for COORDINATE : %d' % coordinate))
            return False

        if coordinate == self.Z_COORDINATE and not QgsWkbTypes.hasZ(layer.wkbType()):
            feedback.reportError(self.tr('Input must have Z coordinate.'), True)
            return False

        if coordinate == self.M_COORDINATE and not QgsWkbTypes.hasM(layer.wkbType()):
            feedback.reportError(self.tr('Input must have M coordinate.'), True)
            return False

        if QgsWkbTypes.isMultiType(layer.wkbType()):
            feedback.reportError(self.tr('Multipart geometries are not currently supported'), True)
            return False

        self.coordinate = coordinate
        self.nodata = self.parameterAsDouble(parameters, self.NODATA, context) or None
        self.smooth_window = self.parameterAsInt(parameters, self.SMOOTH_WINDOW, context)
        self.noise_power = self.parameterAsDouble(parameters, self.NOISE_POWER, context) or None

        return True

    def processFeature(self, feature, context, feedback): #pylint: disable=no-self-use,unused-argument,missing-docstring

        from scipy import signal

        smooth_window = self.smooth_window
        noise_power = self.noise_power
        nodata = self.nodata

        if noise_power is not None and noise_power <= 0:
            feedback.reportError(
                self.tr('Noise power shoud be a positive double value or None'),
                False)
            noise_power = None

        if self.coordinate == self.Z_COORDINATE:

            def transform(geometry):
                """
                Filter Zs using a Wiener filter
                """

                z = np.array([v.z() for v in geometry.vertices()])

                if z.shape[0] == 0:
                    return geometry

                z[z != nodata] = signal.wiener(z[z != nodata], smooth_window, noise_power)

                points = list()

                for i, vertex in enumerate(geometry.vertices()):
                    vertex.setZ(float(z[i]))
                    points.append(vertex)

                return QgsLineString(points)

        elif self.coordinate == self.M_COORDINATE:

            def transform(geometry):
                """
                Filter Ms using a Wiener filter
                """

                m = np.array([v.m() for v in geometry.vertices()])

                if m.shape[0] == 0:
                    return geometry

                m[m != nodata] = signal.wiener(m[m != nodata], smooth_window, noise_power)

                points = list()

                for i, vertex in enumerate(geometry.vertices()):
                    vertex.setM(float(m[i]))
                    points.append(vertex)

                return QgsLineString(points)

        # else:
        #   Never happens

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
