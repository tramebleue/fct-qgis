# -*- coding: utf-8 -*-

"""
Terrain Analysis Algorithms

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
from .FlowAccumulation import FlowAccumulation
from .TopologicalStreamBurn import TopologicalStreamBurn

def terrain_algorithms():

    return [
        DetrendDEM(),
        FlowAccumulation(),
        TopologicalStreamBurn()
    ]
