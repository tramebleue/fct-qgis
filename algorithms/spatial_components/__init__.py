# -*- coding: utf-8 -*-

"""
Spatial Components Algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from .DetrendDEM import DetrendDEM
from .DisaggregatePolygon import DisaggregatePolygon
from .PolygonSkeleton import PolygonSkeleton
from .ValleyBottom import ValleyBottom
from .ValleyCenterLine import ValleyCenterLine

def spatial_componentsAlgorithms():

    return [
        DetrendDEM(),
        DisaggregatePolygon(),
        PolygonSkeleton(),
        ValleyBottom(),
        ValleyCenterLine()
    ]
