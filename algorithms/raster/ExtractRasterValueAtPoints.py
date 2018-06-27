# -*- coding: utf-8 -*-

"""
***************************************************************************
    SegmentMeanSlope.py
    ---------------------
    Date                 : February 2018
    Copyright            : (C) 2018 by Christophe Rousson
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
__date__ = 'February 2018'
__copyright__ = '(C) 2018, Christophe Rousson'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

from qgis.core import QgsFeature, QgsField
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterString
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog
from osgeo import gdal
from osgeo import osr
import numpy as np

class ElevationService(object):

    def __init__(self, datasource, band, nodata, datasource_srid,  input_srid):
        self.datasource = datasource
        self.band = band
        self.nodata = nodata
        self.datasource_srid = datasource_srid
        self.input_srid = input_srid

    def __enter__(self):
        INPUT_SRS = osr.SpatialReference()
        INPUT_SRS.ImportFromEPSG(self.input_srid)
        DATA_SRS = osr.SpatialReference()
        DATA_SRS.ImportFromEPSG(self.datasource_srid)
        self.input_transform = osr.CreateCoordinateTransformation(INPUT_SRS, DATA_SRS)
        self.dem = gdal.Open(self.datasource)
        self.elevations = self.dem.GetRasterBand(1)
        return self

    def __exit__(self,  exc_type, exc_val, exc_tb):
        self.input_transform = None
        self.elevations = None
        self.dem = None

    def in_range(self, px, py):
        return (px >= 0) and (py >= 0) and (px < self.dem.RasterXSize) and (py < self.dem.RasterYSize)

    def worldtopixel(self, x, y):
        dem_tranform = self.dem.GetGeoTransform()
        px = int((x - dem_tranform[0]) / dem_tranform[1])
        py = int((y - dem_tranform[3]) / dem_tranform[5])
        return (px, py)

    def point_elevation(self, point):
        """ Returns point elevation (z) according to DEM

        Input:
        - point: QgsPoint
        """
        t = self.input_transform.TransformPoint(point.x(), point.y())
        px, py = self.worldtopixel(t[0], t[1])
        # TODO check point is within data range, otherwise return 0
        if not self.in_range(px, py):
            return self.nodata
        elev = self.elevations.ReadAsArray(px, py, 1, 1).ravel()
        return np.asscalar(elev[0])

    def line_elevation(self, linestring, step):
        """ Returns projected linestring
            as a sequence of (x, y, z, m) coordinates
            where is the 'measure' coordinate,
            ie. curvilinear coordinate of point measured along line

        Input:
        - linestring: QgsGeometry of type LineString
        - measure z every step along line, given in map units
        """
        length = linestring.length()
        for s in np.arange(0, length+step, step):
            p = linestring.interpolate(s).asPoint()
            yield p.x(), p.y(), self.point_elevation(p), s

def fixed_precision(x, precision):
    return round(float(x) * precision) / precision


class ExtractRasterValueAtPoints(GeoAlgorithm):

    INPUT_POINTS = 'INPUT_POINTS'
    INPUT_RASTER = 'INPUT_RASTER'
    INPUT_RASTER_BAND = 'INPUT_RASTER_BAND'
    VALUE_FIELD = 'VALUE_FIELD'
    # NODATA = 'NODATA'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Extract Raster Value At Points')
        self.group, self.i18n_group = self.trAlgorithm('Tools for Rasters')

        self.addParameter(ParameterVector(self.INPUT_POINTS,
                                          self.tr('Input Points'), [ParameterVector.VECTOR_TYPE_POINT]))

        self.addParameter(ParameterRaster(self.INPUT_RASTER,
                                          self.tr('Input Raster')))

        self.addParameter(ParameterNumber(self.INPUT_RASTER_BAND,
                                          self.tr('Band'), default=1, minValue=1))

        self.addParameter(ParameterString(self.VALUE_FIELD,
                                          self.tr('Value Field'), default='VALUE'))

        # self.addParameter(ParameterNumber(self.NODATA,
        #                                   self.tr('No Data Value'), default=-999.0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Raster Values')))

    def processAlgorithm(self, progress):
        
        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_POINTS))
        raster_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_RASTER))
        auth1, code1 = layer.crs().authid().split(':')
        auth2, code2 = raster_layer.crs().authid().split(':')

        value_field = self.getParameterValue(self.VALUE_FIELD)
        band = self.getParameterValue(self.INPUT_RASTER_BAND)
        nodata = raster_layer.dataProvider().srcNoDataValue(band)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            layer.fields().toList() + [
                QgsField(value_field, QVariant.Double, len=10, prec=4)
            ],
            layer.dataProvider().geometryType(),
            layer.crs())
        
        total = 100.0 / layer.featureCount()

        with ElevationService(raster_layer.dataProvider().dataSourceUri(), band, nodata, int(code2), int(code1)) as service:
            
            for current, feature in enumerate(vector.features(layer)):

                value = service.point_elevation(feature.geometry().asPoint())
                # ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "Point %s value = %.3f" % (str(feature.geometry().asPoint()), value))

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [
                        value
                    ])
                writer.addFeature(outfeature)

                progress.setPercentage(int(current * total))



