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
from osgeo import (
    gdal,
    osr
)

from qgis.core import ( # pylint: disable=import-error,no-name-in-module
    QgsGeometry,
    QgsPoint,
    QgsPointXY
)

# pylint: disable=invalid-name

class RasterDataAccess(object):
    """ Read raster values through GDAL API
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
        px = round((x - dem_tranform[0]) / dem_tranform[1] - 0.5)
        py = round((y - dem_tranform[3]) / dem_tranform[5] - 0.5)
        return px, py

    def pixeltoworld(self, px, py):
        """ Transform raster pixel coordinates (px, py)
            into real world coordinates (x, y)
        """
        dem_tranform = self.dem.GetGeoTransform()
        x = (px + 0.5)*dem_tranform[1] + dem_tranform[0]
        y = (py + 0.5)*dem_tranform[5] + dem_tranform[3]
        return x, y

    def value(self, point):
        """ Returns point value (z) according to DEM

        Parameters
        ----------
        point: QgsPointXY
        """

        t = self.input_transform.TransformPoint(point.x(), point.y())
        px, py = self.worldtopixel(t[0], t[1])

        if not self.in_range(px, py):
            return self.nodata

        elev = self.data.ReadAsArray(px, py, 1, 1).ravel()
        return elev[0]

    def window(self, point, width, height):
        """ Returns point value (z) according to DEM

        Parameters
        ----------
        point: QgsPointXY, real world coordinate of window center
        width: float, real world width of window
        height: float, real world height of window

        Returns
        -------

        NumPy array of data (2-dimensional)
        """

        t = self.input_transform.TransformPoint(point.x(), point.y())
        px, py = self.worldtopixel(t[0], t[1])
        dem_tranform = self.dem.GetGeoTransform()
        dx = round(width / dem_tranform[1])
        dy = round(height / -dem_tranform[5])

        if not (self.in_range(px - dx//2, py - dy//2) and
                self.in_range(px - dx//2 + dx, py - dy//2 + dy)):
            return None

        return self.data.ReadAsArray(px - dx//2, py - dy//2, dx, dy)

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

        points = linestring.asPolyline()
        m0 = 0.0
        for a, b in zip(points[:-1], points[1:]):
            for x, y, z, m in self.segment(a, b):
                yield x, y, z, m0 + m
            m0 = m0 + QgsGeometry.fromPointXY(a).distance(QgsGeometry.fromPointXY(b))

        yield b.x(), b.y(), self.value(b), m0

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

        dem_tranform = self.dem.GetGeoTransform()
        rx = dem_tranform[1]
        ry = -dem_tranform[5]

        if dx > 0.0 or dy > 0.0:

            if dx > dy:
                n = dx / rx
                dx = rx
                dy = dy / n
            else:
                n = dy / ry
                dy = ry
                dx = dx / n

            if a.x() > b.x():
                dx = -dx
            if a.y() > b.y():
                dy = -dy

        def project(x0, y0):
            """ Project point on segment [AB]
                Return True if the intersection is between A and B,
                and the (x, y) coordinates of the intersection.
            """

            # x0, y0 = self.pixeltoworld(px, py)
            ux = b.x() - a.x()
            uy = b.y() - a.y()
            k = ((x0-a.x())*ux + (y0-a.y())*uy) / (ux**2+uy**2)
            x = a.x() + k*ux
            y = a.y() + k*uy
            return (k >= 0 and k <= 1), x, y

        i = 0
        yield a.x(), a.y(), self.value(a), 0.0
        # start pixel
        # px, py = self.worldtopixel(a.x(), a.y())
        x0, y0 = self.pixeltoworld(*self.worldtopixel(a.x(), a.y()))
        onsegment, x, y = project(x0, y0)

        def point(i):
            """ Return i-th point in segment direction
            """
            x = a.x() + i*dx
            y = a.y() + i*dy
            # return self.worldtopixel(x, y)
            return x, y

        while not onsegment:

            if i > 5:
                break

            i += 1
            px, py = point(i)
            onsegment, x, y = project(px, py)

        x1 = a.x()
        y1 = b.x()
        m = 0.0

        while onsegment:

            m += QgsPoint(x, y).distance(QgsPoint(x1, y1))
            yield x, y, self.value(QgsPointXY(x, y)), m
            i += 1
            px, py = point(i)
            x1, y1 = x, y
            onsegment, x, y = project(px, py)



    def segment2(self, a, b):
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

        dem_tranform = self.dem.GetGeoTransform()
        rx = dem_tranform[1]
        ry = -dem_tranform[5]

        if dx > 0.0 or dy > 0.0:

            if dx > dy:
                n = dx / rx
                dx = rx
                dy = dy / n
                interceptx = True
            else:
                n = dy / ry
                dy = ry
                dx = dx / n
                interceptx = False

            if a.x() > b.x():
                dx = -dx
            if a.y() > b.y():
                dy = -dy

            x = a.x()
            y = a.y()
            yield x, y, self.value(a), 0.0

            # # Align sample points on raster grid

            # # 1. set start point
            # x0, y0 = self.pixeltoworld(*self.worldtopixel(x, y))
            # if interceptx:
            #     x1 = x0
            #     y1 = y + (x0-x)*dy/dx
            #     if np.sign(dx)*np.sign(x-x0) == 1:
            #         x = x1 + dx
            #         y = y1 + dy
            #         i = 1.0
            #     else:
            #         x = x1
            #         y = y1
            #         i = 0.0
            # else:
            #     x1 = x + (y0-y)*dx/dy
            #     y1 = y0
            #     if np.sign(dy)*np.sign(y-y0) == 1:
            #         x = x1 + dx
            #         y = y1 + dy
            #         i = 1.0
            #     else:
            #         x = x1
            #         y = y1
            #         i = 0.0

            # # 2. set number of iterations needed to reach B
            # x0, y0 = self.pixeltoworld(*self.worldtopixel(b.x(), b.y()))
            # if interceptx:
            #     if np.sign(dx)*np.sign(b.x()-x0) == -1:
            #         n = n - 1
            # else:
            #     if np.sign(dy)*np.sign(b.y()-y0) == -1:
            #         n = n - 1

            # Iterate along segment

            dm = sqrt(dx*dx + dy*dy)
            m = 0.0
            # i = 0.0

            while i < n-0.5:

                z = self.value(QgsPointXY(x, y))
                yield x, y, z, m

                x = x + dx
                y = y + dy
                m = m + dm
                i = i + 1.0

            # z = self.value(b)
            # yield b.x(), b.y(), z, b.distance(a)

        else:

            z = self.value(a)
            yield x, y, z, 0.0
            # yield x, y, z, 0.0
