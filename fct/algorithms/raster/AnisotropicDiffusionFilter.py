# -*- coding: utf-8 -*-

"""
Anisotropic Diffusion (Perona-Malik) Filter 

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from osgeo import gdal

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessingAlgorithm,
    QgsProcessingParameterBand,
    QgsProcessingParameterEnum,
    QgsProcessingParameterNumber,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from processing.algs.gdal.GdalUtils import GdalUtils # pylint:disable=import-error

from ...lib.anisotropic import anisotropic_diffusion
from ..metadata import AlgorithmMetadata

class AnisotropicDiffusionFilter(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Apply a Perona-Malik filter to raster.

    The Perona-Malik filter is an edge-preserving, anisotropic diffusion filter.

    References
    ----------

    [1] P. Perona and J. Malik.
       Scale-space and edge detection using ansotropic diffusion.
       IEEE Transactions on Pattern Analysis and Machine Intelligence,
       12(7):629-639, July 1990.

    [2] M.J. Black, G. Sapiro, D. Marimont, D. Heeger
       Robust anisotropic diffusion.
       IEEE Transactions on Image Processing,
       7(3):421-432, March 1998.
    """

    METADATA = AlgorithmMetadata.read(__file__, 'AnisotropicDiffusionFilter')

    # anisotropic_diffusion(img, niter=1, kappa=50, gamma=0.1, voxelspacing=None, option=1)

    INPUT = 'INPUT'
    BANDS = 'BANDS'
    ITERATIONS = 'ITERATIONS'
    KAPPA = 'KAPPA'
    GAMMA = 'GAMMA'
    METHOD = 'METHOD'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config=None): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.INPUT,
            self.tr('Input Raster')))

        self.addParameter(QgsProcessingParameterBand(
            self.BANDS,
            self.tr('Bands To Process'),
            parentLayerParameterName=self.INPUT,
            allowMultiple=True,
            defaultValue=[1]))

        self.addParameter(QgsProcessingParameterNumber(
            self.ITERATIONS,
            self.tr('Number of Iterations'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=1,
            defaultValue=1))

        self.addParameter(QgsProcessingParameterNumber(
            self.KAPPA,
            self.tr('Conduction coefficient Kappa'),
            type=QgsProcessingParameterNumber.Integer,
            minValue=0,
            defaultValue=50))

        self.addParameter(QgsProcessingParameterNumber(
            self.GAMMA,
            self.tr('Diffusion rate'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0,
            defaultValue=0.25))

        self.addParameter(QgsProcessingParameterEnum(
            self.METHOD,
            self.tr('Diffusion function'),
            options=map(self.tr, [
                'Perona-Malik exponential function',
                'Perona-Malik inverse function',
                'Tukey biweight function'
            ]),
            defaultValue=1))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Filtered (Anisotropic Diffusion)')))

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        raster = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        bands = self.parameterAsInts(parameters, self.BANDS, context)
        iterations = self.parameterAsInt(parameters, self.ITERATIONS, context)
        kappa = self.parameterAsInt(parameters, self.KAPPA, context)
        gamma = self.parameterAsDouble(parameters, self.GAMMA, context)
        method = self.parameterAsInt(parameters, self.METHOD, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        ds = gdal.OpenEx(raster.dataProvider().dataSourceUri(), gdal.GA_ReadOnly)
        transform = ds.GetGeoTransform()

        driver_name = GdalUtils.getFormatShortNameFromFilename(output)
        driver = gdal.GetDriverByName(driver_name or 'GTiff')

        dst = driver.Create(
            output,
            xsize=ds.RasterXSize,
            ysize=ds.RasterYSize,
            bands=len(bands),
            eType=gdal.GDT_Float32,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        dst.SetProjection(ds.GetProjection())

        total = 100.0 / len(bands) if bands else 0.0

        for i, n in enumerate(bands):

            if feedback.isCanceled():
                break

            band = ds.GetRasterBand(n)
            data = band.ReadAsArray()
            nodata = band.GetNoDataValue()

            out = anisotropic_diffusion(data, iterations, kappa, gamma, (transform[1], -transform[5]), method+1)
            out[data == nodata] = nodata

            dst_band = dst.GetRasterBand(i+1)
            dst_band.WriteArray(out)
            dst_band.SetNoDataValue(nodata)
            del dst_band

            feedback.setProgress(int(i*total))

        ds = dst = None

        return {self.OUTPUT: output}
