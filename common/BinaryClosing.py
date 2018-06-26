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

import numpy

try:
    from scipy.stats.mstats import mode
    hasSciPy = True
except:
    hasSciPy = False

from osgeo import gdal, ogr, osr
from qgis.core import QgsRectangle, QgsGeometry, QgsFeature, QgsFields, QgsField
from PyQt4.QtCore import QVariant

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.GeoAlgorithmExecutionException import GeoAlgorithmExecutionException
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterString
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputRaster
from processing.tools.raster import mapToPixel
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

class BinaryClosing(GeoAlgorithm):

    INPUT = 'INPUT'
    BAND = 'BAND'
    OUTPUT = 'OUTPUT'
    DISTANCE = 'DISTANCE'
    ITERATIONS = 'ITERATIONS'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Binary Closing')
        self.group, self.i18n_group = self.trAlgorithm('Image Processing')

        self.addParameter(ParameterRaster(self.INPUT,
                                          self.tr('Raster layer')))

        self.addParameter(ParameterNumber(self.BAND,
                                          self.tr('Raster band'), 1, 999, 1))

        self.addParameter(ParameterNumber(self.DISTANCE,
                                          self.tr('Structuring Distance (Map unit)'), default=50.0, minValue=0.0))

        self.addParameter(ParameterNumber(self.ITERATIONS,
                                          self.tr('Iterations'), default=1, minValue=0))

        self.addOutput(OutputRaster(self.OUTPUT, self.tr('Binary Closing Result')))

    def processAlgorithm(self, progress):

        rasterPath = unicode(self.getParameterValue(self.INPUT))
        bandNumber = self.getParameterValue(self.BAND)
        distance = self.getParameterValue(self.DISTANCE)
        iterations = self.getParameterValue(self.ITERATIONS)

        datasource = gdal.Open(rasterPath, gdal.GA_ReadOnly)
        geotransform = datasource.GetGeoTransform()
        pixel_xsize = geotransform[1]
        pixel_ysize = -geotransform[5]

        try:
            from scipy.ndimage.morphology import binary_closing, generate_binary_structure, iterate_structure
        except ImportError:
            raise GeoAlgorithmExecutionException('SciPy ndimage.morphology module is not available.')

        size = int(round(distance / pixel_xsize))
        structure = iterate_structure(generate_binary_structure(2, 1), (size - 3) / 2)

        progress.setText('Read input ...')
        mat = datasource.GetRasterBand(bandNumber).ReadAsArray()
        nodata = datasource.GetRasterBand(bandNumber).GetNoDataValue()
        mat[mat == nodata] = 0

        progress.setText('SciPy Morphology Closing ...')
        mat = binary_closing(mat, structure=structure, iterations=iterations)

        output = self.getOutputFromName(self.OUTPUT).getCompatibleFileName(self)
        progress.setText('Write output to %s ...' % output)
        driver = gdal.GetDriverByName('GTiff')
        # dst = gdal.Create(output, datasource.GetRasterXSize, datasource.GetRasterYSize, 1, strict=0, options=[ 'TILED=YES', 'COMPRESS=DEFLATE' ])
        dst = driver.CreateCopy(output, datasource, strict=0, options=[ 'TILED=YES', 'COMPRESS=DEFLATE' ])
        dst.GetRasterBand(bandNumber).WriteArray(mat)

        del mat
        del datasource
        del dst