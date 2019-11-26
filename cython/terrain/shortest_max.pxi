# -*- coding: utf-8 -*-

"""
Shortest Maximum

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
def shortest_max(
        float[:, :] data,
        float nodata,
        float startval=0,
        float[:, :] out=None,
        float[:, :] distance=None,
        feedback=None):
    """
    shortest_max(data, nodata, startval=0, out=None, distance=None, feedback=None)
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
                out[i, j] = data[i, j]

    # Djiskstra iteration

    while not queue.empty():

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
            out[i, j] = max[float](data[i, j], out[ix, jx])
            ancestors.erase(ij)

        else:

            out[i, j] = data[i, j]

        distance[i, j] = d
        seen[i, j] = 2 # settled
        
        count += 1
        progress1 = int(count*total)

        if progress1 > progress0:
        
            if feedback.isCanceled():
                break
        
            feedback.setProgress(progress1)
            progress0 = progress1

        for x in range(8):

            ix = i + ci[x]
            jx = j + cj[x]

            if not ingrid(height, width, ix, jx):
                continue

            if data[ix, jx] == nodata:
                continue

            if ci[x] == 0 or cj[x] == 0:
                dx = d + 1
            else:
                dx = d + 1.4142135623730951 # sqrt(2)

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