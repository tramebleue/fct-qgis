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
include "burnfill.pxi"
include "flow_accumulation.pxi"
include "streams.pxi"
include "watershed.pxi"
include "watershed2.pxi"
include "labels.pxi"
include "graph.pxi"
include "resolve_flat.pxi"
include "stream_flow.pxi"
include "watershed_max.pxi"
include "shortest_distance.pxi"
include "shortest_max.pxi"
include "shortest_ref.pxi"
include "shortest_ref_ws.pxi"