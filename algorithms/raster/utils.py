# -*- coding: utf-8 -*-

"""
Raster utilities

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from math import sqrt
import numpy as np
import gdal
import osr

from qgis.core import (
    QgsGeometry,
    QgsPointXY
)

# pylint: disable=invalid-name

class RasterDataAccess(object):
    """ Read raster values
    """

    def __init__(self, datasource, datasource_srid, input_srid=None, band=1):
        self.datasource = datasource
        self.band = band
        self.datasource_srid = datasource_srid
        self.input_srid = input_srid or datasource_srid
        self.dem = None
        self.data = None
        self.nodata = None
        self.input_transform = None

    def __enter__(self):
        input_srs = osr.SpatialReference()
        input_srs.ImportFromEPSG(self.input_srid)
        data_srs = osr.SpatialReference()
        data_srs.ImportFromEPSG(self.datasource_srid)
        self.input_transform = osr.CreateCoordinateTransformation(input_srs, data_srs)
        self.dem = gdal.Open(self.datasource)
        self.data = self.dem.GetRasterBand(self.band)
        self.nodata = self.data.GetNoDataValue()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.input_transform = None
        self.data = None
        self.nodata = None
        self.dem = None

    def in_range(self, px, py):
        """ Check whether pixel (px, py) is within data range
        """
        return (px >= 0) and (py >= 0) and \
            (px < self.dem.RasterXSize) and (py < self.dem.RasterYSize)

    def worldtopixel(self, x, y):
        """ Transform real world coordinates (x, y)
            into raster pixel coordinates (px, py)
        """
        dem_tranform = self.dem.GetGeoTransform()
        px = int((x - dem_tranform[0]) / dem_tranform[1])
        py = int((y - dem_tranform[3]) / dem_tranform[5])
        return (px, py)

    def value(self, point):
        """ Returns point value (z) according to DEM

        Parameters
        ----------
        point: QgsPointXY
        """

        t = self.input_transform.TransformPoint(point.x(), point.y())
        px, py = self.worldtopixel(*t)

        if not self.in_range(px, py):
            return self.nodata

        elev = self.data.ReadAsArray(px, py, 1, 1).ravel()
        return elev[0]

    def sample_linestring(self, linestring, step):
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
        for measure in np.arange(0, length+step, step):
            point = linestring.interpolate(measure).asPointXY()
            yield point.x(), point.y(), self.value(point), measure

    def linestring(self, linestring):
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

            for points in linestring.asMultiPolylineXY():

                m0 = 0.0
                for a, b in zip(points[:-1], points[1:]):
                    for x, y, z, m in self.segment(a, b):
                        yield x, y, z, m0 + m
                    m0 = m0 + QgsGeometry.fromPointXY(a).distance(QgsGeometry.fromPointXY(b))

        else:

            points = linestring.asPolylineXY()
            m0 = 0.0
            for a, b in zip(points[:-1], points[1:]):
                for x, y, z, m in self.segment(a, b):
                    yield x, y, z, m0 + m
                m0 = m0 + QgsGeometry.fromPointXY(a).distance(QgsGeometry.fromPointXY(b))

    def segment(self, a, b):
        """ Returns projected segment
            as a sequence of (x, y, z, m) coordinates

        Parameters
        ----------
        a, b: QgsPointXY
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

            if a.x() < b.x():
                dx = -dx
            if a.y() < b.y():
                dy = -dy
            dm = sqrt(dx*dx + dy*dy)

            i = 0.0
            m = 0.0
            while i < n:

                z = self.value(QgsPointXY(x, y))
                yield x, y, z, m

                x = x + dx
                y = y + dy
                m = m + dm
                i = i + 1.0
