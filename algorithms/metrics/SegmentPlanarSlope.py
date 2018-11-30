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

from qgis.core import QgsFeature, QgsField, QgsPoint, QgsGeometry
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.Processing import Processing
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.outputs import OutputVector
from processing.core.ProcessingLog import ProcessingLog
from processing.gui.Postprocessing import handleAlgorithmResults
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ...core import vector as vector_helper

from osgeo import gdal
from osgeo import osr
import numpy as np
from math import sqrt, atan2, degrees

class ElevationService(object):

    def __init__(self, datasource, datasource_srid,  input_srid):
        self.datasource = datasource
        self.datasource_srid = datasource_srid
        self.input_srid = input_srid

    def __enter__(self):
        INPUT_SRS = osr.SpatialReference()
        INPUT_SRS.ImportFromEPSG(self.input_srid)
        DATA_SRS = osr.SpatialReference()
        DATA_SRS.ImportFromEPSG(self.datasource_srid)
        self.input_transform = osr.CreateCoordinateTransformation(INPUT_SRS, DATA_SRS)
        self.dem = gdal.Open(self.datasource)
        dem_tranform = self.dem.GetGeoTransform()
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

    def point_elevation(self, point, nodata):
        """ Returns point elevation (z) according to DEM

        Parameters
        ----------

        point: QgsPoint

        Returns
        -------

        z (elevation) at point `point`
        """
        t = self.input_transform.TransformPoint(point.x(), point.y())
        px, py = self.worldtopixel(t[0], t[1])
        # TODO check point is within data range, otherwise return 0
        if not self.in_range(px, py):
            return nodata
        elev = self.elevations.ReadAsArray(px, py, 1, 1).ravel()
        return elev[0]

    def sample_linestring(self, linestring, step, nodata):
        """ Returns projected linestring
            as a sequence of (x, y, z, m) coordinates
            where m is the 'measure' coordinate,
            ie. curvilinear coordinate of point measured along line

        Parameters
        ----------
        
        linestring: QgsGeometry, type LineString
            Input feature
        
        step: float
            measure z every `step` along line,
            given in map units
        """
        length = linestring.length()
        for s in np.arange(0, length+step, step):
            p = linestring.interpolate(s).asPoint()
            yield p.x(), p.y(), self.point_elevation(p, nodata), s

    def project_linestring(self, linestring, nodata):
        """ Returns projected linestring
            as a sequence of (x, y, z, m) coordinates
            where m is the 'measure' coordinate,
            ie. curvilinear coordinate of point measured along line

        Parameters
        ----------
        
        linestring: QgsGeometry, type LineString
        
        nodata: float
            elevation value to return
            when point falls out of raster grid

        Returns
        -------

        Generator of (x, y, z, m) coordinates
        corresponding to the intersection of raster cells with input linestring,
        yielding one data point per intersected cell.

        """

        if linestring.isMultipart():

            # Does it make sense to use a MultiLineString as input ??

            for points in linestring.asMultiPolyline():

                m0 = 0.0
                for a, b in zip(points[:-1], points[1:]):
                    for x, y, z, m in self.project_segment(a, b, nodata):
                            yield x, y, z, m0 + m
                    m0 = m0 + QgsGeometry.fromPoint(a).distance(QgsGeometry.fromPoint(b))

        else:

            points = linestring.asPolyline()
            m0 = 0.0
            for a, b in zip(points[:-1], points[1:]):
                for x, y, z, m in self.project_segment(a, b, nodata):
                        yield x, y, z, m0 + m
                m0 = m0 + QgsGeometry.fromPoint(a).distance(QgsGeometry.fromPoint(b))

    def project_segment(self, a, b, nodata):
        """ Returns projected segment
            as a sequence of (x, y, z, m) coordinates

        Parameters
        ----------
        a, b: QgsPoint
            end points of segment [AB]
        
        nodata: float
            elevation value to return
            when point falls out of raster grid

        Returns
        -------
        Generator of (x, y, z, m) coordinates
        corresponding to the intersection of raster cells with segment [AB],
        yielding one data point per intersected cell.

        """

        dx = abs(b.x() - a.x())
        dy = abs(b.y() - a.y())
        x = a.x()
        y = a.y()

        if dx > 0.0 or dy > 0.0:

            if dx > dy:
                n = dx / self.dem.RasterXSize
                dx = self.dem.RasterXSize
                dy = dy / n
            else:
                n = dy / self.dem.RasterYSize
                dy = self.dem.RasterYSize
                dx = dx / n

            if a.x() < b.x(): dx = -dx
            if a.y() < b.y(): dy = -dy
            dm = sqrt(dx*dx + dy*dy)

            i = 0.0
            m = 0.0
            while i < n:

                z = self.point_elevation(QgsPoint(x, y), nodata)
                yield x, y, z, m

                x = x + dx
                y = y + dy
                m = m + dm
                i = i + 1.0

def fixed_precision(x, precision):
    return round(float(x) * precision) / precision

def azimuth(tangle):
    """
    Converts trigonometric angle (counter-clockwise from east axis)
    to geographic angle (clockwise from north axis)

    Input and output angles are expressed in decimal degrees.

    Parameter
    ---------

    tangle: float
        Trigonometric angle in degrees

    Returns
    -------

    Geographic azimuth in degrees (float).
    """

    if tangle > 90:
        return -tangle + 90 + 360
    else:
        return -tangle + 90


class SegmentPlanarSlope(GeoAlgorithm):

    INPUT_LINESTRINGS = 'INPUT_LINESTRINGS'
    INPUT_DEM = 'INPUT_DEM'
    LINE_ORDERING = 'LINE_ORDERING'
    MEASURE_STEP = 'MEASURE_STEP'
    NODATA = 'NODATA'
    OUTPUT = 'OUTPUT'

    def defineCharacteristics(self):
        
        self.name, self.i18n_name = self.trAlgorithm('Segment Planar Slope')
        self.group, self.i18n_group = self.trAlgorithm('Metrics')

        self.addParameter(ParameterVector(self.INPUT_LINESTRINGS,
                                          self.tr('Input Linestrings'), [ParameterVector.VECTOR_TYPE_LINE]))

        self.addParameter(ParameterRaster(self.INPUT_DEM,
                                          self.tr('Elevations (DEM)')))

        # self.addParameter(ParameterNumber(self.MEASURE_STEP,
        #                                   self.tr('Measure Step (Map Unit)'), default=5.0, minValue=0.0))

        self.addParameter(ParameterNumber(self.NODATA,
                                          self.tr('No Data Value'), default=-999.0))

        self.addParameter(ParameterSelection(self.LINE_ORDERING,
                                             self.tr('Line Ordering'),
                                             options=['Up-Down', 'Down-Up'], default=0))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Detrending Parameters')))

    def processAlgorithm(self, progress):
        
        line_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_LINESTRINGS))
        dem_layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_DEM))
        auth1, code1 = line_layer.crs().authid().split(':')
        auth2, code2 = dem_layer.crs().authid().split(':')

        # measure_step = self.getParameterValue(self.MEASURE_STEP)
        nodata = self.getParameterValue(self.NODATA)

        updown_ordering = (self.getParameterValue(self.LINE_ORDERING) == 0)

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            vector_helper.createUniqueFieldsList(
                line_layer,
                QgsField('DX', QVariant.Double, len=10, prec=6),
                QgsField('DY', QVariant.Double, len=10, prec=6),
                QgsField('Z0', QVariant.Double, len=10, prec=6),
                QgsField('SLOPE', QVariant.Double, len=10, prec=6),
                QgsField('SLDIR', QVariant.Double, len=10, prec=6)
            ),
            line_layer.dataProvider().geometryType(),
            line_layer.crs())
        
        total = 100.0 / line_layer.featureCount()

        with ElevationService(dem_layer.dataProvider().dataSourceUri(), int(code2), int(code1)) as service:
            
            for current, feature in enumerate(vector.features(line_layer)):

                X = np.array([[ x, y, z ] for x, y, z, m in service.project_linestring(feature.geometry(), nodata) ])
                Z = np.array(X[:,2])
                X[:,2] = 1.0
                A, res, rank, eigen_values = np.linalg.lstsq(X, Z)

                dx, dy, z0 = A

                outfeature = QgsFeature()
                outfeature.setGeometry(feature.geometry())
                outfeature.setAttributes(feature.attributes() + [
                        float(dx),
                        float(dy),
                        float(z0),
                        sqrt(float(dx)**2 + float(dy)**2),
                        azimuth(degrees(atan2(dy, dx)))
                    ])
                writer.addFeature(outfeature)

                progress.setPercentage(int(current * total))

