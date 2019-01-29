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
from .LineStringBufferByM import LineStringBufferByM
from .PointsAlongPolygon import PointsAlongPolygon
from .PointsInPolygon import PointsInPolygon
from .PointsMedialAxis import PointsMedialAxis
from .RandomPoissonDiscSamples import RandomPoissonDiscSamples
from .RegularHexSamples import RegularHexSamples
from .RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from .SciPyVoronoiPolygons import SciPyVoronoiPolygons
from .SetMCoordFromMeasureField import SetMCoordFromMeasureField
from .TransformCoordinateByExpression import TransformCoordinateByExpression
from .UniquePoints import UniquePoints

def vector_algorithms():

    return [
        LineMidpoints(),
        LineStringBufferByM(),
        PointsAlongPolygon(),
        PointsInPolygon(),
        PointsMedialAxis(),
        RandomPoissonDiscSamples(),
        RegularHexSamples(),
        RemoveSmallPolygonalObjects(),
        SciPyVoronoiPolygons(),
        SetMCoordFromMeasureField(),
        TransformCoordinateByExpression(),
        UniquePoints()
    ]
