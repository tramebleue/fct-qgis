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

cdef long propagate(
    short[:, :] flow, long height, long width,
    float[:, :] values,
    float nodata,
    long i0, long j0):
    """
    Propagate data values upstream.
    Start from cell (i, j) and move in inverse flow direction
    """

    cdef long i, j, count
    cdef int x, di, dj
    cdef Cell cell
    cdef CellStack stack

    cell = Cell(i0, j0)
    stack.push(cell)
    count = 0

    while not stack.empty():

        cell = stack.top()
        stack.pop()
        i = cell.first
        j = cell.second
        count += 1

        for x in range(8):

            di = ci[x]
            dj = cj[x]

            if ingrid(height, width, i+di, j+dj) and flow[i+di, j+dj] == upward[x]:

                if values[i+di, j+dj] == nodata:
                    values[i+di, j+dj] = values[i, j]

                cell = Cell(i+di, j+dj)
                stack.push(cell)

    return count

@cython.boundscheck(False)
@cython.wraparound(False)
def watershed(short[:, :] flow, float[:, :] values, float nodata, feedback=None):
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

    cdef long height, width, i, j
    cdef short direction
    cdef int x, di, dj, current, progress0, progress1
    cdef float total

    height = flow.shape[0]
    width = flow.shape[1]
    total = 100.0 / (height*width)
    current = 0
    progress0 = progress1 = 0

    if feedback is None:
        feedback = SilentFeedback()

    # Lookup for outlets

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            direction = flow[i, j]

            if direction > -1:

                x = ilog2(direction)
                di = ci[x]
                dj = cj[x]

                # Check if (i,j) flows in nodata or outside grid

                if not ingrid(height, width, i+di, j+dj) or flow[i+di, j+dj] == -1:

                    current += propagate(
                        flow, height, width, values, nodata,
                        i, j)

                    progress1 = int(current*total)
                    if progress1 > progress0:
                        feedback.setProgress(progress1)
                        progress0 = progress1
