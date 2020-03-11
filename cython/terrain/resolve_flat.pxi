# -*- coding: utf-8 -*-

"""
Drainage (flow) direction for DEM flats

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from cython.operator cimport dereference, preincrement

@cython.boundscheck(False)
@cython.wraparound(False)
def resolve_flat(
        float[:, :] elevations,
        short[:, :] flow,
        feedback=None):
    """
    Create a pseudo-height raster for DEM flats,
    suitable to calculate a realistic drainage direction raster.

    Parameters
    ----------

    elevations: array-like, ndims=2, dtype=float32
        Elevation raster,
        preprocessed for depression filling.
        Flats must have constant elevation.

    flow: array-like, ndims=2, dtype=int16,
        D8 Flow (Drainage) direction raster,
        with same shape as `elevations`

    feedback: QgsFeedback-like object

    Returns
    -------

    flat_mask: float32 array
        Pseudo-height raster,
        with same shape as `elevations`,
        nodata = 0

    labels: uint32 array
        Flat labels,
        with same shape as `elevations`,
        nodata = 0
    """

    cdef:

        Cell c
        # list low_queue, high_queue, edge_queue, queue
        deque[Cell] low_queue, high_queue, edge_queue
        deque[Cell].iterator it
        list queue, flatcells
        # dict flat_heights
        map[int, int] flat_heights
        long i, j, xi, xj, current, n_flats = 0
        int x, increment
        float z
        short direction
        double total

        int[:, :] flat_mask
        unsigned int[:, :] labels
        unsigned int label, next_label
        unsigned char[:, :] seen
        bint is_edge_outlet, is_receiving_flow, is_flat
        
        int slope_gradient = -3
        int outlet_gradient = 5

    # low_queue = list()
    # high_queue = list()
    # edge_queue = list()
    # flat_labels = np.unique(labels[labels > 0])
    height = elevations.shape[0]
    width = elevations.shape[1]

    if feedback is None:
        feedback = SilentFeedback()

    # Find flats boundary cells

    feedback.setProgressText('Find flat boundary cells ...')
    total = 100.0 / (height*width)
    FLOW_NODATA = -1
    NO_FLOW = 0

    for i in range(height):
        for j in range(width):

            direction = flow[i, j]
            z = elevations[i, j]

            if direction == FLOW_NODATA:
                continue

            is_edge_outlet = False
            is_receiving_flow = False
            is_flat = False

            for x in range(8):

                xi = i + ci[x]
                xj = j + cj[x]

                if not ingrid(height, width, xi, xj):
                    if direction == NO_FLOW:
                        is_edge_outlet = True
                    continue

                if flow[xi, xj] == FLOW_NODATA:
                    if direction == NO_FLOW:
                        is_edge_outlet = True
                    continue

                if z == elevations[xi, xj]:
                    is_flat = True

                if direction != NO_FLOW and flow[xi, xj] == NO_FLOW and z == elevations[xi, xj]:
                    # cell (i, j) is part of a flat (same elevation as neighbor)
                    # but flows outside the flat : it is a flat outlet
                    # low_queue.append((i, j))
                    low_queue.push_back(Cell(i, j))
                    is_edge_outlet = False
                    break

                elif direction == NO_FLOW and z < elevations[xi, xj]:
                    # cell (i, j) is part of a flat
                    # and has a higher neighbor that flows into this flat
                    is_receiving_flow = True
                    # do not reset is_edge_outlet flag :
                    # cell can also be an edge outlet
                    # is_edge_outlet = False

            if is_receiving_flow:
                # high_queue.append((i, j))
                high_queue.push_back(Cell(i, j))

            if is_edge_outlet:
                # edge_queue.append((i, j))
                edge_queue.push_back(Cell(i, j))

            if is_flat:
                n_flats += 1

        feedback.setProgress(int(total * i * width))

    feedback.setProgressText('Low queue : %d, High queue : %d' % (low_queue.size(), high_queue.size()))

    # Label flats

    feedback.setProgressText('Label flats ...')
    labels = np.zeros((height, width), dtype=np.uint32)
    next_label = 1
    total = 100.0 / (low_queue.size() + high_queue.size() + edge_queue.size())

    flatcells = list()

    it = low_queue.begin()
    while it != low_queue.end():
        c = dereference(it)
        flatcells.append((c.first, c.second))
        preincrement(it)

    it = edge_queue.begin()
    while it != edge_queue.end():
        c = dereference(it)
        flatcells.append((c.first, c.second))
        preincrement(it)

    it = high_queue.begin()
    while it != high_queue.end():
        c = dereference(it)
        flatcells.append((c.first, c.second))
        preincrement(it)

    for current, (i, j) in enumerate(flatcells):

        feedback.setProgress(int(current * total))

        queue = [(i, j)]
        z = elevations[i, j]
        label = labels[i, j]

        if label == 0:
            label = next_label
            next_label += 1

        while queue:

            xi, xj = queue.pop(0)

            if not ingrid(height, width, xi, xj):
                continue
            if elevations[xi, xj] != z:
                continue
            if labels[xi, xj] != 0:
                continue

            labels[xi, xj] = label

            for x in range(8):
                queue.append((xi+ci[x], xj+cj[x]))

    del flatcells
    feedback.setProgressText('Found %d flats, %d flat cells' % (next_label-1, n_flats))

    # For each flat,
    # combine flow from high terrain and flow to low_terrain

    # flat_heights = dict()
    flat_mask = np.zeros((height, width), dtype=np.int32)
    increment_marker = (-1, -1)
    total = 100.0 / n_flats if n_flats > 0 else 0.0

    # Process flow away from higher terrain

    feedback.setProgressText('Process flow away from higher terrain')
        
    seen = np.zeros((height, width), dtype=np.uint8)

    it = high_queue.begin()
    # for i, j in high_queue:
    while it != high_queue.end():
        c = dereference(it)
        # seen[i, j] = 1
        seen[c.first, c.second] = 1
        preincrement(it)

    # high_queue.append(increment_marker)
    high_queue.push_back(Cell(-1, -1))
    increment = 1
    current = 0

    while not high_queue.empty():

        # i, j = high_queue.pop(0)
        c = high_queue.front()
        high_queue.pop_front()
        i = c.first
        j = c.second

        if i == -1 and j == -1:
            if not high_queue.empty():
                increment += 1
                # high_queue.append(increment_marker)
                high_queue.push_back(Cell(-1, -1))
                continue
            else:
                break

        current += 1
        # feedback.setProgressText('%d, (%d, %d)' % (current, i, j))
        feedback.setProgress(int(total*current))

        label = labels[i, j]
        assert(label > 0)

        flat_mask[i, j] = increment
        flat_heights[label] = increment

        for x in range(8):

            xi = i + ci[x]
            xj = j + cj[x]

            if ingrid(height, width, xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] == 0 \
                and seen[xi, xj] == 0:

                seen[xi, xj] = 1
                # high_queue.append((xi, xj))
                high_queue.push_back(Cell(xi, xj))

    flat_mask = slope_gradient * np.int32(flat_mask)

    # Process flow toward lower terrain

    feedback.setProgressText('Process flow toward lower terrain')
        
    seen = np.zeros((height, width), dtype=np.uint8)

    # for i, j in (low_queue + edge_queue):
    #     seen[i, j] = 1

    it = low_queue.begin()
    while it != low_queue.end():
        c = dereference(it)
        # seen[i, j] = 1
        seen[c.first, c.second] = 1
        preincrement(it)

    it = edge_queue.begin()
    while it != edge_queue.end():
        c = dereference(it)
        # seen[i, j] = 1
        seen[c.first, c.second] = 1
        preincrement(it)

    # low_queue.append(increment_marker)
    low_queue.push_back(Cell(-1, -1))
    increment = 1

    while not low_queue.empty():

        # i, j = low_queue.pop(0)

        c = low_queue.front()
        low_queue.pop_front()
        i = c.first
        j = c.second

        if i == -1 and j == -1:
            if not low_queue.empty():
                increment += 1
                # low_queue.append(increment_marker)
                low_queue.push_back(Cell(-1, -1))
                continue
            else:
                break

        label = labels[i, j]
        assert(label > 0)

        if flat_mask[i, j] < 0:
            flat_mask[i, j] = flat_mask[i, j] + outlet_gradient*flat_heights[label] + outlet_gradient*increment
        else:
            flat_mask[i, j] = outlet_gradient*increment

        for x in range(8):

            xi = i + ci[x]
            xj = j + cj[x]

            if ingrid(height, width, xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] <= 0 \
                and seen[xi, xj] == 0:
                
                seen[xi, xj] = 1
                # low_queue.append((xi, xj))
                low_queue.push_back(Cell(xi, xj))

    # Process flow toward nodata edges

    feedback.setProgressText('Process flow toward no-data edges')

    # edge_queue.append(increment_marker)
    edge_queue.push_back(Cell(-1, -1))
    increment = 1

    while not edge_queue.empty():

        # i, j = edge_queue.pop(0)

        c = edge_queue.front()
        edge_queue.pop_front()
        i = c.first
        j = c.second

        if i == -1 and j == -1:
            if not edge_queue.empty():
                increment += 1
                # edge_queue.append(increment_marker)
                edge_queue.push_back(Cell(-1, -1))
                continue
            else:
                break

        label = labels[i, j]
        assert(label > 0)

        if flat_mask[i, j] < 0:
            flat_mask[i, j] = flat_mask[i, j] + outlet_gradient*flat_heights[label] + outlet_gradient*increment
        else:
            flat_mask[i, j] = outlet_gradient*increment

        for x in range(8):

            xi = i + ci[x]
            xj = j + cj[x]

            if ingrid(height, width, xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] <= 0 \
                and seen[xi, xj] == 0:
                
                seen[xi, xj] = 1
                # edge_queue.append((xi, xj))
                edge_queue.push_back(Cell(xi, xj))

    feedback.setProgress(100)

    return np.float32(flat_mask), np.uint32(labels)

@cython.boundscheck(False)
@cython.wraparound(False)
def flat_mask_flowdir(
    float[:, :] mask,
    short[:, :] flow,
    unsigned int[:, :] labels):
    """
    Assign drainage directon to flat areas, according to pseudo-height in `mask`.
    Input `flow` raster is modified in place.

    See also resolve_flat()

    Parameters
    ----------

    mask: float32 2d-array
        Pseudo-height raster

    flow: int16 2d-array
        D8 Flow Direction raster

    labels: uint32 2d-array
        Flat labels

    Returns
    -------

    Modified D8 Flow Direction NumPy array, nodata = -1

    """

    cdef:

        long width, height
        long i, j, x, xmin, ix, jx
        float z, zx, zmin
        unsigned int label

    height = mask.shape[0]
    width = mask.shape[1]

    with nogil:

        for i in range(height):
            for j in range(width):

                # if flow[i, j] == -1: # FLOW_NODATA
                #     continue

                if flow[i, j] != 0: # NO_FLOW
                    continue

                label = labels[i, j]
                z = mask[i, j]
                zmin = z
                xmin = -1 # NO_FLOW

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]
                    
                    if not ingrid(height, width, ix, jx):
                        # if xmin == -1:
                        #     xmin = x
                        continue

                    if labels[ix, jx] != label:
                        continue

                    zx = mask[ix, jx]

                    if zx < zmin:
                        zmin = zx
                        xmin = x

                if xmin == -1:
                    flow[i, j] = 0 # NO_FLOW
                else:
                    flow[i, j] = pow2(xmin)

    return np.int16(flow)