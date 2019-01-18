# -*- coding: utf-8 -*-

"""
Watershed Analysis

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from .grid import (
    D8POW2_UPWARD,
    D8_SEARCH,
    ingrid
)

def watershed(flow, values, nodata, feedback=None):
    """
    Watershed analysis

    Fills no-data cells in `values`
    by propagating data values in the inverse (ie. upstream) flow direction
    given by `flow`.
    Modifies `values` in place.

    In typical usage,
    `values` is the Strahler order for stream cells and no data elsewhere,
    and the result is a raster map of watersheds,
    identified by their Strahler order.

    Parameters
    ----------

    flow: array-like
        D8 flow direction raster, dtype=int8, nodata=-1 (ndim=2)

    values: array-like
        Values to propagate upstream, same shape as `flow`, any data

    nodata: number
        No-data value in `values`

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback
    """

    height, width = flow.shape
    total = 100.0 / (height*width)

    # Lookup for outlets

    for i in range(height):

        feedback.setProgress(int(i*width*total))
        if feedback.isCanceled():
            break

        for j in range(width):

            direction = flow[i, j]

            if direction > -1:

                x = int(np.log2(direction))
                di, dj = D8_SEARCH[x]

                # Check if (i,j) flows in nodata or outside grid

                if not ingrid(flow, i+di, j+dj) or flow[i+di, j+dj] == -1:

                    propagate(flow, values, nodata, i, j, feedback)

def propagate(flow, values, nodata, i0, j0, feedback=None):
    """
    Propagate data values upstream.
    Start from cell (i, j) and move in inverse flow direction
    """

    stack = [(i0, j0)]

    while stack:

        if feedback.isCanceled():
            break

        i, j = stack.pop()

        for x in range(8):

            di, dj = D8_SEARCH[x]

            if ingrid(flow, i+di, j+dj) and flow[i+di, j+dj] == D8POW2_UPWARD[x]:

                if values[i+di, j+dj] == nodata:
                    values[i+di, j+dj] = values[i, j]

                stack.append((i+di, j+dj))
