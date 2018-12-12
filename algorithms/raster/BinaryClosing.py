# -*- coding: utf-8 -*-

"""
***************************************************************************
    ZonalStatistics.py
    ---------------------
    Date                 : August 2013
    Copyright            : (C) 2013 by Alexander Bruy
    Email                : alexander dot bruy at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Alexander Bruy'
__date__ = 'August 2013'
__copyright__ = '(C) 2013, Alexander Bruy'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

try:
    from scipy.ndimage.morphology import binary_closing
    hasSciPy = True
except ImportError:
    hasSciPy = False

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingException,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterDestination)

import numpy as np
import gdal

class BinaryClosing(QgsProcessingAlgorithm):

    INPUT = 'INPUT'
    BAND = 'BAND'
    OUTPUT = 'OUTPUT'
    DISTANCE = 'DISTANCE'
    ITERATIONS = 'ITERATIONS'

    def name(self):
      return 'BinaryClosing'

    def groupId(self):
      return 'Tools for Rasters'

    def displayName(self):
      return self.tr(self.name())

    def group(self):
      return self.tr(self.groupId())

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT,
                                          self.tr('Raster layer')))

        self.addParameter(QgsProcessingParameterNumber(self.BAND,
                                          self.tr('Raster band'), defaultValue=1))

        self.addParameter(QgsProcessingParameterNumber(self.DISTANCE,
                                          self.tr('Structuring Distance (Map unit)'), defaultValue=50.0, minValue=0.0))

        self.addParameter(QgsProcessingParameterNumber(self.ITERATIONS,
                                          self.tr('Iterations'), defaultValue=1, minValue=0))

        self.addParameter(QgsProcessingParameterRasterDestination(self.OUTPUT, self.tr('Binary Closing Result')))

    def disk(self, radius, dtype=np.uint8):
        """
        Generates a flat, disk-shaped structuring element.
        A pixel is within the neighborhood if the euclidean distance between
        it and the origin is no greater than radius.
        Parameters
        ----------
        radius : int
            The radius of the disk-shaped structuring element.
        Other Parameters
        ----------------
        dtype : data-type
            The data type of the structuring element.
        Returns
        -------
        selem : ndarray
            The structuring element where elements of the neighborhood
            are 1 and 0 otherwise.
        """
        L = np.arange(-radius, radius + 1)
        X, Y = np.meshgrid(L, L)
        return np.array((X ** 2 + Y ** 2) <= radius ** 2, dtype=dtype)

    def processAlgorithm(self, parameters, context, feedback):
        
        if not hasSciPy:
            raise QgsProcessingException(self.tr('SciPy morphology libraries not found.'))

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        rasterPath = str(raster.dataProvider().dataSourceUri())

        bandNumber = self.parameterAsInt(parameters, self.BAND, context)
        distance = self.parameterAsDouble(parameters, self.DISTANCE, context)
        iterations = self.parameterAsOutputLayer(parameters, self.ITERATIONS, context)

        datasource = gdal.Open(rasterPath, gdal.GA_ReadOnly)
        geotransform = datasource.GetGeoTransform()
        pixel_xsize = geotransform[1]
        pixel_ysize = -geotransform[5]

        size = int(round(distance / pixel_xsize))
        structure = self.disk(distance)

        feedback.pushInfo('Read input ...')
        mat = datasource.GetRasterBand(bandNumber).ReadAsArray()
        nodata = datasource.GetRasterBand(bandNumber).GetNoDataValue()
        mat[mat == nodata] = 0

        feedback.pushInfo('SciPy Morphology Closing ...')
        mat = binary_closing(mat, structure=structure, iterations=iterations)

        output = self.getOutputFromName(self.OUTPUT).getCompatibleFileName(self)
        feedback.pushInfo('Write output to %s ...' % output)
        driver = gdal.GetDriverByName('GTiff')
        # dst = gdal.Create(output, datasource.GetRasterXSize, datasource.GetRasterYSize, 1, strict=0, options=[ 'TILED=YES', 'COMPRESS=DEFLATE' ])
        dst = driver.CreateCopy(output, datasource, strict=0, options=[ 'TILED=YES', 'COMPRESS=DEFLATE' ])
        dst.GetRasterBand(bandNumber).WriteArray(mat)

        del mat
        del datasource
        del dst

    def tr(self, string):
        return QCoreApplication.translate('FluvialCorridorToolbox', string)

    def createInstance(self):
      return BinaryClosing()