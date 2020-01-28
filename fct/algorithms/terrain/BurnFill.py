# -*- coding: utf-8 -*-

"""
TopologicalStreamBurn

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
import numpy as np

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterNumber,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterRasterDestination,
    QgsProcessingParameterRasterLayer
)

from .StreamToRaster import worldtopixel, rasterize_linestring

from ..metadata import AlgorithmMetadata

class BurnFill(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Compute flow direction raster,
    using a variant of Wang and Liu priority flood algorithm
    that processes stream cell in before other cells.

    References
    -----

    [1] Lindsay, J. B. (2016).
        The Practice of DEM Stream Burning Revisited.
        Earth Surface Processes and Landforms, 41(5), 658‑668. 
        https://doi.org/10.1002/esp.3888

    [2] WhiteboxGAT Java implementation (Last modified 2 Oct 2017)
        https://github.com/jblindsay/whitebox-geospatial-analysis-tools/blob/038b9c7/resources/plugins/Scripts/TopologicalBreachBurn.groovy
    """

    METADATA = AlgorithmMetadata.read(__file__, 'BurnFill')

    ELEVATIONS = 'ELEVATIONS'
    STREAMS = 'STREAMS'
    PK_FIELD = 'PK_FIELD'
    ZDELTA = 'ZDELTA'
    OUTPUT = 'OUTPUT'
    FILLED = 'FILLED'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterRasterLayer(
            self.ELEVATIONS,
            self.tr('Elevations')))

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.STREAMS,
            self.tr('Stream LineString'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.PK_FIELD,
            self.tr('Stream Primary Key'),
            parentLayerParameterName=self.STREAMS,
            defaultValue='GID'))

        self.addParameter(QgsProcessingParameterNumber(
            self.ZDELTA,
            self.tr('Minimum Z Delta Between Cells'),
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0,
            defaultValue=0.0005))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUTPUT,
            self.tr('Flow Direction')))

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.FILLED,
            self.tr('Depression-Filled DEM'),
            optional=True,
            createByDefault=False))

    def canExecute(self): #pylint: disable=unused-argument,missing-docstring

        try:
            # pylint: disable=import-error,unused-variable
            from ...lib.terrain_analysis import burnfill
            return True, ''
        except ImportError:
            return False, self.tr('Missing dependency: FCT terrain_analysis')

    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        from ...lib.terrain_analysis import burnfill

        elevations_lyr = self.parameterAsRasterLayer(parameters, self.ELEVATIONS, context)
        layer = self.parameterAsSource(parameters, self.STREAMS, context)
        pk_field = self.parameterAsString(parameters, self.PK_FIELD, context)
        zdelta = self.parameterAsDouble(parameters, self.ZDELTA, context)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)
        filled = self.parameterAsOutputLayer(parameters, self.FILLED, context)

        elevations_ds = gdal.Open(elevations_lyr.dataProvider().dataSourceUri())
        elevations = elevations_ds.GetRasterBand(1).ReadAsArray()
        nodata = elevations_ds.GetRasterBand(1).GetNoDataValue()

        transform = elevations_ds.GetGeoTransform()
        width = elevations_ds.RasterXSize
        height = elevations_ds.RasterYSize

        feedback.setProgressText('Rasterize stream vectors')
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0.0

        streams = np.zeros((height, width), dtype=np.float32)
        junctions = np.zeros((height, width), dtype=np.uint8)

        def isdata(px, py):
            """
            True if (py, px) is a valid pixel coordinate
            """

            return px >= 0 and py >= 0 and px < width and py < height

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            link_id = feature.attribute(pk_field)

            linestring = worldtopixel(np.array([
                (point.x(), point.y())
                for point in feature.geometry().asPolyline()
            ]), transform)

            for a, b in zip(linestring[:-1], linestring[1:]):
                for col, row in rasterize_linestring(a, b):
                    if isdata(col, row):
                        current_value = streams[row, col]
                        if current_value == 0 or link_id < current_value:
                            # Override with the smallest ID
                            streams[row, col] = link_id

            # col, row = linestring[-1]
            # junctions[row, col] = 1

        feedback.setProgressText('Mark junctions cells')

        # We cannot just mark last points as junctions
        # because there can be collisions between links.
        # The solution is to iterate from the end of each link,
        # and find the first cell which has not been erased
        # by another link :
        # this is the junction to the rest of the network

        for current, feature in enumerate(layer.getFeatures()):

            if feedback.isCanceled():
                break

            feedback.setProgress(int(current*total))

            link_id = feature.attribute(pk_field)

            linestring = worldtopixel(np.array([
                (point.x(), point.y())
                for point in feature.geometry().asPolyline()
            ]), transform)

            for i in range(linestring.shape[0]-1, -1, -1):

                px, py = linestring[i]

                if px < 0 or py < 0 or px >= width or py >= height:
                    continue

                if streams[py, px] == link_id:
                    junctions[py, px] = 1
                    break

        feedback.setProgressText('Priority flood')

        flow = burnfill(
            elevations,
            streams,
            junctions,
            nodata,
            zdelta,
            feedback=feedback)

        if feedback.isCanceled():
            feedback.reportError(self.tr('Aborted'), True)
            return {}

        feedback.setProgress(100)
        feedback.pushInfo(self.tr('Write flow direction ...'))

        driver = gdal.GetDriverByName('GTiff')

        dst = driver.Create(
            output,
            xsize=elevations_ds.RasterXSize,
            ysize=elevations_ds.RasterYSize,
            bands=1,
            eType=gdal.GDT_Int16,
            options=['TILED=YES', 'COMPRESS=DEFLATE'])
        dst.SetGeoTransform(transform)
        # dst.SetProjection(srs.exportToWkt())
        dst.SetProjection(elevations_lyr.crs().toWkt())

        dst.GetRasterBand(1).WriteArray(flow)
        dst.GetRasterBand(1).SetNoDataValue(-1)

        # Properly close GDAL resources
        dst = None

        if filled:

            feedback.pushInfo(self.tr('Write modified elevations ...'))

            dst = driver.Create(
                filled,
                xsize=elevations_ds.RasterXSize,
                ysize=elevations_ds.RasterYSize,
                bands=1,
                eType=gdal.GDT_Float32,
                options=['TILED=YES', 'COMPRESS=DEFLATE'])
            dst.SetGeoTransform(transform)
            # dst.SetProjection(srs.exportToWkt())
            dst.SetProjection(elevations_lyr.crs().toWkt())

            dst.GetRasterBand(1).WriteArray(elevations)
            dst.GetRasterBand(1).SetNoDataValue(nodata)

            # Properly close GDAL resources
            dst = None

        # Properly close GDAL resources
        elevations_ds = None
        streams_ds = None

        return {
            self.OUTPUT: output,
            self.FILLED: filled
        }
