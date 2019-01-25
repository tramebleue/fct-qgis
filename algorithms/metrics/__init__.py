# -*- coding: utf-8 -*-

"""
Metrics Algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from .AggregateFeatures import AggregateFeatures
from .KnickPoints import KnickPoints
from .LineStringZSlope import LineStringZSlope
from .OrthogonalTransects import OrthogonalTransects

def metrics_algorithms():

    return [
        AggregateFeatures(),
        KnickPoints(),
        LineStringZSlope(),
        OrthogonalTransects()
    ]
