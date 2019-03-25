# -*- coding: utf-8 -*-

"""
Flow Accumulation - Cython implementation

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
def flow_accumulation(short[:,:] flow, unsigned int[:,:] out=None, feedback=None):
    """ Flow accumulation from D8 flow direction.

    Parameters
    ----------

    flow: array-like
        D8 Flow direction raster (ndim=2, dtype=np.int8), nodata=-1

    out: array-like
        Same shape as flow, dtype=np.uint32, initialized to 0

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback

    Returns
    -------

    Flow accumulation raster, dtype=np.uint32, nodata=-1
    """

    cdef long width, height
    cdef float nodata, total
    cdef long i, j, ix, jx, count
    cdef int x, progress0, progress1
    cdef signed char[:,:] inflow
    cdef signed char inflowij
    cdef short direction
    cdef long ncells = 0
    cdef Cell cell
    cdef CellStack stack

    if feedback is None:
        feedback = SilentFeedback()

    height = flow.shape[0]
    width = flow.shape[1]
    nodata = -1

    if out is None:
        out = np.full((height, width), 0, dtype=np.uint32)

    inflow = np.full((height, width), -1, dtype=np.int8)

    # progress = TermProgressBar(2*width*height)
    # progress.write('Input is %d x %d' % (width, height))
    feedback.setProgressText('Find source cells ...')
    total = 100.0 / (width*height)
    progress0 = progress1 = 0
    # progress = CppTermProgress(height*width)
    # progress.write('Find source cells ...')

    # with nogil:

    for i in range(height):
        for j in range(width):

            direction = flow[i, j]

            if direction != nodata:

                out[i, j] = 1
                inflowij = 0

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if ingrid(height, width, ix, jx) and (flow[ix, jx] == upward[x]):
                        inflowij += 1

                if inflowij == 0:
                    cell = Cell(i, j)
                    stack.push(cell)

                inflow[i, j] = inflowij
                ncells += 1

            # progress.update(1)
        progress1 = int((i*width+j)*total)
        if progress1 > progress0:
            feedback.setProgress(progress1)
            progress0 = progress1
            if feedback.isCanceled():
                break

    # progress = CppTermProgress(ncells)
    # progress.write('Accumulate ...')
    feedback.setProgressText('Accumulate ...')
    count = 0
    progress0 = progress1 = 0

    while not stack.empty():

        cell = stack.top()
        stack.pop()
        i = cell.first
        j = cell.second

        inflow[i, j] = -1

        direction = flow[i, j]
        if direction == 0:
            # progress.update(1)
            count += 1
            continue

        x = ilog2(direction)
        ix = i + ci[x]
        jx = j + cj[x]

        while ingrid(height, width, ix, jx) and inflow[ix, jx] > 0:

            out[ix, jx] = out[ix, jx] + out[i, j]
            inflow[ix, jx] = inflow[ix, jx] - 1

            # check if we reached a confluence cell

            if inflow[ix, jx] > 0:
                break

            # otherwise accumulate downward

            direction = flow[ix, jx]
            if direction == 0:
                # progress.update(1)
                count += 1
                break

            inflow[ix, jx] = -1
            i = ix
            j = jx
            x = ilog2(direction)
            ix = i + ci[x]
            jx = j + cj[x]

            # progress.update(1)
            count += 1

        progress1 = int(count*total)
        if progress1 > progress0:
            feedback.setProgress(progress1)
            progress0 = progress1
            if feedback.isCanceled():
                break

        count += 1

    return out

ctypedef unsigned int ContributingArea

@cython.boundscheck(False)
@cython.wraparound(False)
def stream_contributing_area(ContributingArea[:, :] acc, float[:, :] streams):

    cdef:

        long height = acc.shape[0], width = acc.shape[1]
        long i, j
        float stream
        ContributingArea area
        map[float, ContributingArea] maxarea

    assert(height == streams.shape[0])
    assert(width == streams.shape[1])

    with nogil:

        for i in range(height):
            for j in range(width):

                stream = streams[i, j]

                if stream != 0:
                    area = acc[i, j]
                    if maxarea.count(stream) == 0:
                        maxarea[stream] = area
                    else:
                        maxarea[stream] = max[ContributingArea](area, maxarea[stream])

    return maxarea