# -*- coding: utf-8 -*-

"""
***************************************************************************
    DifferentialRasterThreshold.py
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

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterString
from processing.core.outputs import OutputRaster
from processing.core.ProcessingLog import ProcessingLog
# import gdalnumeric as gn
from osgeo import gdal
import numpy as np


class DifferentialRasterThreshold(GeoAlgorithm):

    INPUT_DEM = 'INPUT_DEM'
    REFERENCE_DEM = 'REFERENCE_DEM'
    MIN_THRESHOLD = 'MIN_THRESHOLD'
    MAX_THRESHOLD = 'MAX_THRESHOLD'
    RELATIVE_DEM = 'OUTPUT'
    # NO_DATA = 'NO_DATA'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Differential Raster Threshold')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Rasters')

        self.addParameter(ParameterRaster(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(ParameterRaster(self.REFERENCE_DEM,
                                          self.tr('Reference DEM')))
        self.addParameter(ParameterNumber(self.MIN_THRESHOLD,
                                          self.tr('Min. value'), default=-10))
        self.addParameter(ParameterNumber(self.MAX_THRESHOLD,
                                          self.tr('Max. value'), default=10))
        
        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addOutput(OutputRaster(self.RELATIVE_DEM, self.tr('Relative DEM')))

    def processAlgorithm(self, progress):

        input_dem_path = self.getParameterValue(self.INPUT_DEM)
        reference_dem_path = self.getParameterValue(self.REFERENCE_DEM)
        minvalue = self.getParameterValue(self.MIN_THRESHOLD)
        maxvalue = self.getParameterValue(self.MAX_THRESHOLD)
        output_path = self.getOutputValue(self.RELATIVE_DEM)
        # ndv = float(self.getParameterValue(self.NO_DATA))

        # dem = gn.LoadFile(input_dem_path)
        ds = gdal.Open(input_dem_path)
        if ds.RasterCount != 1:
            ProcessingLog.addToLog(ProcessingLog.LOG_WARNING, self.tr("Input DEM has more than 1 band."))

        dem = ds.GetRasterBand(1).ReadAsArray()
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        dem = np.ma.masked_where(dem == nodata, dem)
        
        # reference = gn.LoadFile(reference_dem_path)
        refds = gdal.Open(reference_dem_path)
        if refds.RasterCount != 1:
            ProcessingLog.addToLog(ProcessingLog.LOG_WARNING, self.tr("Reference DEM has more than 1 band."))
        
        reference = refds.GetRasterBand(1).ReadAsArray()
        ref_nodata = refds.GetRasterBand(1).GetNoDataValue()
        if ref_nodata is None:
            ref_nodata = nodata

        reference = np.ma.masked_where(reference == ref_nodata, reference)
        
        relative = dem - reference
        mask = np.bitwise_and(relative > minvalue, relative <= maxvalue)

        # gn.SaveArray(mask.astype(np.uint8), str(output_path), format='GTiff', prototype=str(input_dem_path))
        driver = gdal.GetDriverByName('GTiff')
        dst = driver.CreateCopy(str(output_path), ds, strict=0, options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.GetRasterBand(1).WriteArray(mask.astype(np.uint8))

        # Properly close GDAL resources
        ds = None
        refds = None
        dst = None

