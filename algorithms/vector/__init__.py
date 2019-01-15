# -*- coding: utf-8 -*-

"""
Vector General Algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from .LineMidpoints import LineMidpoints
from .PointsAlongPolygon import PointsAlongPolygon
from .PointsInPolygon import PointsInPolygon
from .PointsMedialAxis import PointsMedialAxis
from .RandomPoissonDiscSampling import RandomPoissonDiscSampling
from .RegularHexPoints import RegularHexPoints
from .RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from .SciPyVoronoiPolygons import SciPyVoronoiPolygons

def vector_algorithms():

    return [
        LineMidpoints(),
        PointsAlongPolygon(),
        PointsInPolygon(),
        PointsMedialAxis(),
        RandomPoissonDiscSampling(),
        RegularHexPoints(),
        RemoveSmallPolygonalObjects(),
        SciPyVoronoiPolygons()
    ]
