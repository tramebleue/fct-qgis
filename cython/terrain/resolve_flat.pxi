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

        list low_queue, high_queue, edge_queue, queue
        dict flat_heights
        long i, j, xi, xj, current
        int x, increment
        float z
        short direction
        double total

        int[:, :] flat_mask
        unsigned int[:, :] labels
        unsigned int label, next_label
        unsigned char[:, :] seen
        bint is_edge_outlet, is_receiving_flow

    low_queue = list()
    high_queue = list()
    edge_queue = list()
    # flat_labels = np.unique(labels[labels > 0])
    height = elevations.shape[0]
    width = elevations.shape[1]

    # Find flats boundary cells

    feedback.setProgressText('Find flat boundary cells ...')
    total = 100.0 / (height*width)
    FLOW_NODATA = -1
    NO_FLOW = 0

    if feedback is None:
        feedback = SilentFeedback()

    for i in range(height):
        for j in range(width):

            direction = flow[i, j]
            z = elevations[i, j]

            if direction == FLOW_NODATA:
                continue

            is_edge_outlet = False
            is_receiving_flow = False

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

                if direction != NO_FLOW and flow[xi, xj] == NO_FLOW and z == elevations[xi, xj]:
                    # cell (i, j) is part of a flat (same elevation as neighbor)
                    # but flows outside the flat : it is a flat outlet
                    low_queue.append((i, j))
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
                high_queue.append((i, j))

            if is_edge_outlet:
                edge_queue.append((i, j))

        feedback.setProgress(int(total * i * width))

    feedback.setProgressText('Low queue : %d, High queue : %d' % (len(low_queue), len(high_queue)))

    # Label flats

    feedback.setProgressText('Label flats ...')
    labels = np.zeros((height, width), dtype=np.uint32)
    next_label = 1
    total = 100.0 / (len(low_queue) + len(high_queue) + len(edge_queue))

    for current, (i, j) in enumerate(low_queue + high_queue + edge_queue):

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

    feedback.setProgressText('Found %d flats' % (next_label-1))

    # For each flat,
    # combine flow from high terrain and flow to low_terrain

    flat_heights = dict()
    flat_mask = np.zeros((height, width), dtype=np.int32)
    increment_marker = (-1, -1)

    # Process flow away from higher terrain

    feedback.setProgressText('Process flow away from higher terrain')
        
    seen = np.zeros((height, width), dtype=np.uint8)

    for i, j in high_queue:
        seen[i, j] = 1

    high_queue.append(increment_marker)
    increment = 1

    while high_queue:

        i, j = high_queue.pop(0)

        if (i, j) == increment_marker:
            if high_queue:
                increment += 1
                high_queue.append(increment_marker)
                continue
            else:
                break

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
                high_queue.append((xi, xj))

    flat_mask = -np.int32(flat_mask)

    # Process flow toward lower terrain

    feedback.setProgressText('Process flow toward lower terrain')
        
    seen = np.zeros((height, width), dtype=np.uint8)

    for i, j in (low_queue + edge_queue):
        seen[i, j] = 1

    low_queue.append(increment_marker)
    increment = 1

    while low_queue:

        i, j = low_queue.pop(0)

        if (i, j) == increment_marker:
            if low_queue:
                increment += 1
                low_queue.append(increment_marker)
                continue
            else:
                break

        label = labels[i, j]
        assert(label > 0)

        if flat_mask[i, j] < 0:
            flat_mask[i, j] = flat_mask[i, j] + flat_heights[label] + 2*increment
        else:
            flat_mask[i, j] = 2*increment

        for x in range(8):

            xi = i + ci[x]
            xj = j + cj[x]

            if ingrid(height, width, xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] <= 0 \
                and seen[xi, xj] == 0:
                
                seen[xi, xj] = 1
                low_queue.append((xi, xj))

    # Process flow toward nodata edges

    feedback.setProgressText('Process flow toward no-data edges')

    edge_queue.append(increment_marker)
    increment = 1

    while edge_queue:

        i, j = edge_queue.pop(0)

        if (i, j) == increment_marker:
            if edge_queue:
                increment += 1
                edge_queue.append(increment_marker)
                continue
            else:
                break

        label = labels[i, j]
        assert(label > 0)

        if flat_mask[i, j] < 0:
            flat_mask[i, j] = flat_mask[i, j] + flat_heights[label] + 2*increment
        else:
            flat_mask[i, j] = 2*increment

        for x in range(8):

            xi = i + ci[x]
            xj = j + cj[x]

            if ingrid(height, width, xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] <= 0 \
                and seen[xi, xj] == 0:
                
                seen[xi, xj] = 1
                edge_queue.append((xi, xj))

    feedback.setProgress(100)

    return np.float32(flat_mask), np.uint32(labels)

@cython.boundscheck(False)
@cython.wraparound(False)
def flat_mask_flowdir(
    float[:, :] mask,
    short[:, :] flow,
    unsigned int[:, :] labels):
    """
    Flow direction from elevation data.

    Assign flow direction toward the lower neighbouring cell.

    Parameters
    ----------

    elevations: array-like, ndims=2, dtype=float32
        Elevation raster

    nodata: float
        No data value for elevation

    Returns
    -------

    int16 D8 Flow Direction NumPy array, nodata = -1

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