# coding: utf-8
# cython: c_string_type=str, c_string_encoding=ascii

"""
Terrain Analysis - Cython implementation of some terrain analysis algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import numpy as np
import cython

cimport numpy as np
cimport cython

# from ta.CppTermProgress cimport CppTermProgress

include "common.pxi"
include "typedef.pxi"
include "fillsinks.pxi"
include "fillsinks2.pxi"
include "flowdir.pxi"
# include "cflowdir.pxi"
# include "cwatershed.pxi"
# include "cstrahler.pxi"
# include "cchannels.pxi"
# include "slope.pxi"
# include "hillshade.pxi"
include "topo_stream_burn.pxi"
include "flow_accumulation.pxi"
include "streams.pxi"
include "watershed.pxi"
include "labels.pxi"
include "graph.pxi"