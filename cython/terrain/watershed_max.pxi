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

@cython.boundscheck(False)
@cython.wraparound(False)
def watershed_max(short[:, :] flow, float[:, :] values, float[:, :] reference, float fill_value=0, feedback=None):
    """
    watershed2(flow, values, fill_value=0, feedback=None)

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

    flow: array-like, dtype=int8, nodata=-1 (ndim=2)
        D8 flow direction raster

    values: array-like, dtype=float32, same shape as `flow`
        Values to propagate upstream

    reference: array-like, dtype=float32, same shape as `flow`
        Values to propagate upstream

    fill_value: float
        Update only cells in `values` having value equal to `fill_value`.
        Other cells are left unchanged.

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback
    """

    cdef:

        long height, width, i, j, ik, jk, ix, jx
        int x, current, progress0, progress1
        float total
        unsigned char[:, :] seen
        cdef Cell cell
        cdef CellStack stack

    height = flow.shape[0]
    width = flow.shape[1]
    total = 100.0 / (height*width)
    current = 0
    progress0 = progress1 = 0

    seen = np.zeros((height, width), dtype=np.uint8)

    if feedback is None:
        feedback = SilentFeedback()

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            if seen[i, j]:
                continue

            if values[i, j] != fill_value:

                cell = Cell(i, j)
                # stack = CellStack()
                stack.push(cell)
                seen[i, j] = True

                while not stack.empty():

                    if feedback.isCanceled():
                        break

                    cell = stack.top()
                    stack.pop()

                    ik = cell.first
                    jk = cell.second

                    for x in range(8):

                        ix = ik + ci[x]
                        jx = jk + cj[x]

                        if ingrid(height, width, ix, jx) and flow[ix, jx] == upward[x] and not seen[ix, jx]:

                            if values[ix, jx] == fill_value:
                                values[ix, jx] = max(values[ik, jk], reference[ik, jk])

                            cell = Cell(ix, jx)
                            stack.push(cell)
                            seen[ix, jx] = True

                    current += 1

                    progress1 = int(current*total)
                    if progress1 > progress0:
                        feedback.setProgress(progress1)
                        progress0 = progress1
