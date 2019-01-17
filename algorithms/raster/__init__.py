# -*- coding: utf-8 -*-

"""
Raster General Algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from .BinaryClosing import BinaryClosing
from .DrapeVectors import DrapeVectors
from .DifferentialRasterThreshold import DifferentialRasterThreshold
from .FocalMean import FocalMean
from .RasterDifference import RasterDifference
from .RasterInfo import RasterInfo

def rasterAlgorithms():

    return [
        BinaryClosing(),
        DrapeVectors(),
        DifferentialRasterThreshold(),
        FocalMean(),
        # ExtractRasterValueAtPoints(),
        # SimpleRasterStatistics()
        RasterDifference(),
        RasterInfo()
    ]
