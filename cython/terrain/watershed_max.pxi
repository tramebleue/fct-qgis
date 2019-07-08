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

cdef long propagate_max(
    short[:, :] flow, long height, long width,
    unsigned char[:, :] values,
    unsigned char[:, :] reference,
    long i0, long j0):
    """
    Propagate data values upstream.
    Start from cell (i0, j0) and move in inverse flow direction
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

                if values[i+di, j+dj] == 0:
                    
                    values[i+di, j+dj] = max(values[i, j], reference[i+di, j+dj])
                    cell = Cell(i+di, j+dj)
                    stack.push(cell)

    return count

@cython.boundscheck(False)
@cython.wraparound(False)
def watershed_max(
    short[:, :] flow,
    unsigned char[:, :] values,
    unsigned char[:, :] reference,
    feedback=None):
    """
    Watershed analysis

    Fills no-data cells in `values`
    by propagating data values in the inverse (ie. upstream) flow direction
    given by `flow`.
    
    Raster `values` will be modified in place.
    
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

    reference: array-like
        Values to propagate upstream, same shape as `flow`, any data

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback
    """

    cdef:

        long height, width, i, j, ix, jx
        short direction
        int x, di, dj, current, progress0, progress1
        float total
        unsigned char[:, :] seen2

    height = flow.shape[0]
    width = flow.shape[1]
    total = 100.0 / (height*width)
    current = 0
    progress0 = progress1 = 0

    if feedback is None:
        feedback = SilentFeedback()

    seen2 = np.zeros((height, width), dtype=np.uint8)

    # Lookup for outlets

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            if flow[i, j] == -1:
                current = current + 1
                continue

            if seen2[i, j] > 0:
                continue

            if flow[i, j] == 0:

                current = current + propagate_max(
                    flow, height, width,
                    values, reference,
                    i, j)

                progress1 = int(current*total)
                if progress1 > progress0:
                    feedback.setProgress(progress1)
                    progress0 = progress1

            else:

                ix = i
                jx = j
                x = ilog2(flow[ix, jx])
                di = ci[x]
                dj = cj[x]

                while ingrid(height, width, ix+di, jx+dj) and flow[ix+di, jx+dj] != -1 and values[ix+di, jx+dj] == 0:

                    ix = ix + di
                    jx = jx + dj
                    
                    if flow[ix, jx] == 0:
                        break

                    x = ilog2(flow[ix, jx])
                    di = ci[x]
                    dj = cj[x]

                    if seen2[ix, jx] == 1:
                        # print('loop....')
                        break

                    seen2[ix, jx] = 1

                # feedback.pushInfo('Propagate values from cell(%d, %d)' % (ix, jx))

                current = current + propagate_max(
                    flow, height, width,
                    values,
                    reference,
                    ix, jx)

            progress1 = int(current*total)
            if progress1 > progress0:
                feedback.setProgress(progress1)
                progress0 = progress1
