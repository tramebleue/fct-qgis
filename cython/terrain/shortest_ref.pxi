# -*- coding: utf-8 -*-

"""
Shortest Reference Value

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
def shortest_ref(
        float[:, :] data,
        float nodata,
        float startval=0,
        float fillval=0,
        float[:, :] cost=None,
        float[:, :] out=None,
        float[:, :] distance=None,
        feedback=None):
    """
    shortest_ref(data, nodata, startval=1, cost=None, out=None, distance=None, feedback=None)

    Assign to each input cell the value of the nearest origin (reference) cell.

    Input Parameters
    ----------------

    data: array-like, ndims=2, dtype=float32
        Origin cells, having value `startval`

    nodata: float
        No-data value in `data`

    startval: float
        Marker value for origin cells in `data`

    cost: array-like, same shape and type as `data`
        Optional cost matrix
        to account for in shortest distance computation.

    Output Parameters
    -----------------

    out: array-like, same shape and type as `data`
        Value of the nearest origin cell.
        `out` is modified in place,
        origin cells value are left unchanged,
        and propagated to nearest neighbors.

    distance: array-like, same shape and type as `data`
        Shortest distance in pixels to the nearest origin cell
        in `data`

    Other Parameters
    ----------------

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback
    """

    cdef:

        long width, height
        long i, j, x, ix, jx, count
        float d, dx, total
        int progress0, progress1

        Cell ij, ijx
        QueueEntry entry
        CellQueue queue
        unsigned char[:, :] seen
        map[Cell, Cell] ancestors

    height = data.shape[0]
    width = data.shape[1]
    seen = np.zeros((height, width), dtype=np.uint8)
    total = 100.0 / (height*width)
    count = 0
    progress0 = progress1 = 0

    if cost is None:
        cost = np.ones((height, width), dtype=np.float32)

    if out is None:
        out = np.full((height, width), startval, dtype=np.float32)

    if distance is None:
        distance = np.zeros((height, width), dtype=np.float32)

    if feedback is None:
        feedback = SilentFeedback()

    # with nogil:

    # Sequential scan
    # Search for origin cells with startvalue

    for i in range(height):
        for j in range(width):

            if data[i, j] == startval:

                entry = QueueEntry(0, Cell(i, j))
                queue.push(entry)
                seen[i, j] = 1 # seen
                distance[i, j] = 0
                # out[i, j] = data[i, j]
                count += 1

            elif data[i, j] != nodata:

                count += 1

    total = 100.0 / count
    count = 0

    # Djiskstra iteration

    while not queue.empty():

        count += 1
        progress1 = int(count*total)

        if progress1 > progress0:
        
            if feedback.isCanceled():
                break
        
            feedback.setProgress(progress1)
            progress0 = progress1

        entry = queue.top()
        queue.pop()

        d = -entry.first
        ij = entry.second
        i = ij.first
        j = ij.second

        if seen[i, j] == 2:
            continue

        if distance[i, j] < d:
            continue

        if ancestors.count(ij) > 0:

            ijx = ancestors[ij]
            ix = ijx.first
            jx = ijx.second
            
            if out[i, j] == fillval:
                out[i, j] = out[ix, jx]
            
            if i == ix or j == jx:
                distance[i, j] = distance[ix, jx] + 1
            else:
                distance[i, j] = distance[ix, jx] + 1.4142135623730951 # sqrt(2)
            
            ancestors.erase(ij)

        else:

            # out[i, j] = data[i, j]
            distance[i, j] = 0
        
        seen[i, j] = 2 # settled

        for x in range(8):

            # D4 connectivity

            # if not (ci[x] == 0 or cj[x] == 0):
            #     continue

            ix = i + ci[x]
            jx = j + cj[x]

            if not ingrid(height, width, ix, jx):
                continue

            if data[ix, jx] == nodata:
                continue

            if ci[x] == 0 or cj[x] == 0:
                dx = 1
            else:
                dx = 1.4142135623730951 # sqrt(2)

            dx = d + dx*cost[ix, jx]

            if seen[ix, jx] == 0:

                ijx = Cell(ix, jx)
                entry = QueueEntry(-dx, ijx)
                queue.push(entry)
                seen[ix, jx] = 1 # seen
                distance[ix, jx] = dx
                ancestors[ijx] = ij

            elif seen[ix, jx] == 1:

                if dx < distance[ix, jx]:

                    ijx = Cell(ix, jx)
                    entry = QueueEntry(-dx, ijx)
                    queue.push(entry)
                    distance[ix, jx] = dx
                    ancestors[ijx] = ij
