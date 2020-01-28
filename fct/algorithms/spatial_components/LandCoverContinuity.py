# -*- coding: utf-8 -*-

"""
Land Cover Continuity Analysis

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
from osgeo import gdal
# import osr

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    # QgsProcessing,
    QgsProcessingAlgorithm,
    # QgsProcessingParameterFeatureSource,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from ..metadata import AlgorithmMetadata

class LandCoverContinuity(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Continuity analysis of land cover from stream network.

    The algorithm performs a shortest path exploration from stream pixels,
    and records the maximum land cover class on the path to every pixel.

    The assumption is that the numeric counts for land cover classes
    reflect an ordering of those classes along a given gradient,
    typically an artificialization gradient (from the most natural/undisturbed
    to the most artificialized/disturbed).

    The resulting map represents the continuity of land cover
    along the gradient of the land cover classes.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'LandCoverContinuity')

    INPUT = 'INPUT'
    STREAM = 'STREAM'
    VALLEYBOTTOM = 'VALLEYBOTTOM'
    DISCONTINUITIES = 'DISCONTINUITIES'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Land Cover Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.STREAM,
            self.tr('Stream Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.VALLEYBOTTOM,
            self.tr('Valley Bottom Raster')))

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.DISCONTINUITIES,
            self.tr('Discontinuitites Raster'),
            optional=True))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Land Cover Continuity')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from ...lib import terrain_analysis as ta

        landcover_lyr = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        stream_lyr = self.parameterAsRasterLayer(parameters, self.STREAM, context)
        valleybottom_lyr = self.parameterAsRasterLayer(parameters, self.VALLEYBOTTOM, context)
        discont_lyr = self.parameterAsRasterLayer(parameters, self.DISCONTINUITIES, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        feedback.setProgressText('Read data')

        landcover_ds = gdal.OpenEx(landcover_lyr.dataProvider().dataSourceUri())
        landcover = landcover_ds.GetRasterBand(1).ReadAsArray()
        nodata = landcover_ds.GetRasterBand(1).GetNoDataValue()
        # height, width = landcover.shape

        stream_ds = gdal.Open(stream_lyr.dataProvider().dataSourceUri())
        stream = stream_ds.GetRasterBand(1).ReadAsArray()
        assert(stream.shape == landcover.shape)

        valleybottom_ds = gdal.Open(valleybottom_lyr.dataProvider().dataSourceUri())
        valleybottom = valleybottom_ds.GetRasterBand(1).ReadAsArray()
        assert(valleybottom.shape == landcover.shape)

        # Mark stream cells as starting point for continuity analysis
        landcover[stream > 0] = 0

        if discont_lyr:

            discont_ds = gdal.Open(discont_lyr.dataProvider().dataSourceUri())
            discont = discont_ds.GetRasterBand(1).ReadAsArray()
            assert(discont.shape == landcover.shape)

            # TODO avoid hardcnding remap and use table parameter
            landcover[(landcover == 51) | (landcover == 53)] = 2
            landcover[discont == 3] = 40
            landcover[discont == 4] = 53

            del discont
            discont_ds = None

        feedback.setProgressText('Perform continuity analysis')

        # Initialize intermediate and output arrays
        out = np.zeros_like(landcover)
        distance = np.zeros_like(landcover)

        # Restrict spatial domain to valley bottom
        landcover[valleybottom != 1] = nodata

        # Cost matrix
        # TODO use table parameter
        cost = np.ones_like(landcover)
        cost[(landcover >= 1) & (landcover < 30)] = 1.0
        cost[(landcover >= 30) & (landcover < 50)] = 10.0
        cost[landcover >= 50] = 100.0

        # Shortest path exploration from stream pixels
        ta.shortest_max(landcover, nodata, 0, cost, out, distance, feedback)

        out[stream > 0] = 1
        out[landcover == nodata] = nodata

        feedback.setProgressText('Write output')

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=landcover_ds.RasterXSize,
            ysize=landcover_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(landcover_ds.GetGeoTransform())
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(landcover_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(out)
        dst.GetRasterBand(1).SetNoDataValue(nodata)

        # Properly close GDAL resources

        landcover_ds = None
        stream_ds = None
        valleybottom_ds = None
        discont_ds = None
        dst = None

        return {self.OUTPUT: output}
