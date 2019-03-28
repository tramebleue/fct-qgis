# -*- coding: utf-8 -*-

"""
Vectorize Stream Features

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

from .grid import (
    D8POW2_UPWARD,
    D8_SEARCH,
    ingrid
)

def stream_to_feature(streams, flow, feedback):
    """
    Extract Stream Segments

    Parameters
    ----------

    flow: array-like
        D8 Flow direction raster (ndim=2)

    streams: array-like
        Rasterize stream network, same shape as `elevations`,
        with stream cells >= 1

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback

    Returns
    -------

    List of stream segments in pixel coordinates.
    """

    height, width = flow.shape
    nodata = -1

    inflow = np.full(flow.shape, -1, dtype=np.int8)

    feedback.setProgressText('Find source cells ...')

    stack = list()
    total = 100.0 / (height*width)
    ncells = 0
    nsegments = 0

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            direction = flow[i, j]

            if direction != nodata and streams[i, j] > 0:

                inflowij = 0

                for x in range(8):

                    di, dj = D8_SEARCH[x]

                    if ingrid(flow, i+di, j+dj) \
                        and streams[i+di, j+dj] > 0 \
                        and (flow[i+di, j+dj] == D8POW2_UPWARD[x]):

                        inflowij += 1

                if inflowij != 1:
                    stack.append((i, j))
                    nsegments += 1

                inflow[i, j] = inflowij
                ncells += 1

        feedback.setProgress(int((i*width)*total))

    feedback.setProgressText('Enumerate segments from upstream to downstream ...')
    total = 100.0 / nsegments
    current = 0
    segments = list()

    while stack:

        if feedback.isCanceled():
            break

        i, j = stack.pop()
        segment = [(j, i)]
        head = inflow[i, j] == 0

        direction = flow[i, j]
        x = int(np.log2(direction))
        di, dj = D8_SEARCH[x]
        i, j = i+di, j+dj

        while ingrid(flow, i, j):

            segment.append((j, i))

            if inflow[i, j] == 1:

                direction = flow[i, j]
                x = int(np.log2(direction))
                di, dj = D8_SEARCH[x]
                i, j = i+di, j+dj

            else:

                break

        current += 1
        feedback.setProgress(int(current*total))

        yield np.array(segment), head
