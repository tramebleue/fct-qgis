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

import numpy as np
from collections import defaultdict
from itertools import count

def resolve_flat(elevations, flow, feedback=None):
    """
    Create a pseudo-height raster for DEM flats,
    suitable to calculate a realistic drainage direction raster.

    Parameters
    ----------

    elevations: array-like, ndims=2, dtype=float32 or float64
        Elevation raster,
        preprocessed for depression filling.
        Flats must have constant elevation.

    flow: array-like, ndims=2, dtype=int16, same shape as `elevations`
        D8 Flow (Drainage) direction raster

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

    low_queue = list()
    high_queue = list()
    edge_queue = list()
    # flat_labels = np.unique(labels[labels > 0])
    height, width = elevations.shape

    def ingrid(i, j):
        return i >= 0 and i < height and j >= 0 and j < width

    D8_SEARCH = np.array([
        [-1, -1,  0,  1,  1,  1,  0, -1],
        [ 0,  1,  1,  1,  0, -1, -1, -1]
    ]).T

    # Find flats boundary cells

    feedback.setProgressText('Find flat boundary cells')
    total = 100.0 / (height*width)
    FLOW_NODATA = -1
    NO_FLOW = 0

    for i in range(height):
        for j in range(width):

            direction = flow[i, j]
            z = elevations[i, j]

            if direction == FLOW_NODATA:
                continue

            is_edge_flow = False
            is_receiving_flow = False

            for x in range(8):

                ci, cj = D8_SEARCH[x]
                xi = i + ci
                xj = j + cj

                if not ingrid(xi, xj):
                    if direction == NO_FLOW:
                        is_edge_flow = True
                    continue

                if flow[xi, xj] == FLOW_NODATA:
                    if direction == NO_FLOW:
                        is_edge_flow = True
                    continue

                if direction != NO_FLOW and flow[xi, xj] == NO_FLOW and z == elevations[xi, xj]:
                    # cell (i, j) is part of a flat (same elevation as neighbor)
                    # but flows outside the flat : it is a flat outlet
                    low_queue.append((i, j))
                    is_edge_flow = False
                    break

                elif direction == NO_FLOW and z < elevations[xi, xj]:
                    # cell (i, j) is part of a flat
                    # and has a higher neighbor that flows into this flat
                    is_receiving_flow = True

            if is_receiving_flow:
                high_queue.append((i, j))

            if is_edge_flow:
                edge_queue.append((i, j))

        feedback.setProgress(int(total * i * width))

    feedback.setProgressText('Low queue : %d, High queue : %d' % (len(low_queue), len(high_queue)))

    # Label flats

    feedback.setProgressText('Label flats ...')
    labels = np.zeros((height, width), dtype=np.uint32)
    label_generator = count(1)
    total = 100.0 / (len(low_queue) + len(high_queue) + len(edge_queue))

    for current, (i, j) in enumerate(low_queue + high_queue + edge_queue):

        feedback.setProgress(int(current * total))

        queue = [(i, j)]
        z = elevations[i, j]
        label = labels[i, j]

        if label == 0:
            label = next(label_generator)

        while queue:

            xi, xj = queue.pop(0)

            if not ingrid(xi, xj):
                continue
            if elevations[xi, xj] != z:
                continue
            if labels[xi, xj] != 0:
                continue

            labels[xi, xj] = label

            for x in range(8):
                ci, cj = D8_SEARCH[x]
                queue.append((xi+ci, xj+cj))

    feedback.setProgressText('Found %d flats' % (next(label_generator) -1))

    # For each flat,
    # combine flow from high terrain and flow to low_terrain

    flat_heights = dict()
    flat_mask = np.zeros((height, width), dtype=np.int32)
    increment_marker = (-1, -1)

    # Process flow away from higher terrain

    feedback.setProgressText('Process flow away from higher terrain')
        
    high_queue.append(increment_marker)
    increment = 1
    seen = np.zeros((height, width), dtype=np.bool)

    for i, j in high_queue:
        seen[i, j] = True

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

            ci, cj = D8_SEARCH[x]
            xi = i + ci
            xj = j + cj

            if ingrid(xi, xj) and labels[xi, xj] == label and flat_mask[xi, xj] == 0 and not seen[xi, xj]:
                seen[xi, xj] = True
                high_queue.append((xi, xj))

    flat_mask = -flat_mask

    # Process flow away toward lower terrain

    feedback.setProgressText('Process flow away toward lower terrain')
        
    low_queue.append(increment_marker)
    increment = 1
    seen = np.zeros((height, width), dtype=np.bool)

    for i, j in (low_queue + edge_queue):
        seen[i, j] = True

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

            ci, cj = D8_SEARCH[x]
            xi = i + ci
            xj = j + cj

            if ingrid(xi, xj) and labels[xi, xj] == label and flat_mask[xi, xj] <= 0 and not seen[xi, xj]:
                seen[xi, xj] = True
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

            ci, cj = D8_SEARCH[x]
            xi = i + ci
            xj = j + cj

            if ingrid(xi, xj) \
                and labels[xi, xj] == label \
                and flat_mask[xi, xj] <= 0 \
                and not seen[xi, xj]:
                
                seen[xi, xj] = True
                edge_queue.append((xi, xj))

    feedback.setProgress(100)

    return np.float32(flat_mask), labels