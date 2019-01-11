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

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessingAlgorithm,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterRasterDestination)
import gdal
import numpy as np

from ..metadata import AlgorithmMetadata

class DifferentialRasterThreshold(AlgorithmMetadata, QgsProcessingAlgorithm):

    METADATA = AlgorithmMetadata.read(__file__, 'DifferentialRasterThreshold')

    INPUT_DEM = 'INPUT_DEM'
    REFERENCE_DEM = 'REFERENCE_DEM'
    MIN_THRESHOLD = 'MIN_THRESHOLD'
    MAX_THRESHOLD = 'MAX_THRESHOLD'
    RELATIVE_DEM = 'OUTPUT'
    # NO_DATA = 'NO_DATA'

    def initAlgorithm(self, config=None):

        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT_DEM,
                                          self.tr('Input DEM')))
        self.addParameter(QgsProcessingParameterRasterLayer(self.REFERENCE_DEM,
                                          self.tr('Reference DEM')))
        self.addParameter(QgsProcessingParameterNumber(self.MIN_THRESHOLD,
                                          self.tr('Min. value'), defaultValue=-10))
        self.addParameter(QgsProcessingParameterNumber(self.MAX_THRESHOLD,
                                          self.tr('Max. value'), defaultValue=10))
        
        # self.addParameter(ParameterString(self.NO_DATA,
        #                                   self.tr('No data value'), '-9999'))

        self.addParameter(QgsProcessingParameterRasterDestination(self.RELATIVE_DEM, self.tr('Relative DEM')))

    def processAlgorithm(self, parameters, context, feedback):

        input_dem = self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
        input_dem_path = str(input_dem.dataProvider().dataSourceUri())

        reference_dem = self.parameterAsRasterLayer(parameters, self.REFERENCE_DEM, context)
        reference_dem_path = str(reference_dem.dataProvider().dataSourceUri())

        maxvalue = self.parameterAsDouble(parameters, self.MAX_THRESHOLD, context)
        minvalue = self.parameterAsDouble(parameters, self.MIN_THRESHOLD, context)

        output_path = self.parameterAsOutputLayer(parameters, self.RELATIVE_DEM, context)
        # ndv = float(self.getParameterValue(self.NO_DATA))

        # dem = gn.LoadFile(input_dem_path)
        ds = gdal.Open(input_dem_path)
        if ds.RasterCount != 1:
            feedback.pushInfo('Input DEM has more than 1 band.')

        dem = ds.GetRasterBand(1).ReadAsArray()
        nodata = ds.GetRasterBand(1).GetNoDataValue()
        dem = np.ma.masked_where(dem == nodata, dem)
        
        # reference = gn.LoadFile(reference_dem_path)
        refds = gdal.Open(reference_dem_path)
        if refds.RasterCount != 1:
            feedback.pushInfo('Reference DEM has more than 1 band.')
        
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

        return {self.RELATIVE_DEM: output_path}


    def tr(self, string):
        return QCoreApplication.translate('FluvialCorridorToolbox', string)

    def createInstance(self):
      return DifferentialRasterThreshold()