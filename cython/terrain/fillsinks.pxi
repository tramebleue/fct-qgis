# -*- coding: utf-8 -*-

"""
Priority Flood Depression Filling

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
def fillsinks(
        float[:, :] elevations,
        float nodata,
        float dx, float dy,
        float minslope=1e-3,
        float[:, :] out = None):
        # short[:, :] flow = None):
    """
    fillsinks(elevations, nodata, dx, dy, minslope, out=None)

    Fill sinks of digital elevation model (DEM),
    based on the algorithm of Wang & Liu (2006).

    Parameters
    ----------

    elevations: array-like
        Digital elevation model (DEM) raster (ndim=2)

    nodata: float
        no-data value in `elevations`    

    dx: float
        raster horizontal resolution in `elevations`

    dy: float
        raster vertical resolution in `elevations`
        (positive value)

    minslope: float
        Minimum slope to preserve between cells
        when filling up sinks.

    out: array-like
        Same shape and dtype as elevations, initialized to nodata

    Returns
    -------

    Flow raster.

    Notes
    -----

    [1] Wang, L. & H. Liu (2006)
        An efficient method for identifying and filling surface depressions
        in digital elevation models.
        International Journal of Geographical Information Science,
        Vol. 20, No. 2: 193-213.

    [2] SAGA C++ Implementation
        https://github.com/saga-gis/saga-gis/blob/1b54363/saga-gis/src/tools/terrain_analysis/ta_preprocessor/FillSinks_WL_XXL.cpp
        GPL Licensed
    """

    cdef long width, height

    cdef long i, j, x, xmin, ix, jx
    cdef float z, zx, zmin
    cdef Cell ij
    cdef QueueEntry entry
    cdef CellQueue queue

    cdef np.ndarray[double, ndim=2] w
    cdef np.ndarray[float] mindiff
    # cdef CppTermProgress progress

    height = elevations.shape[0]
    width = elevations.shape[1]
    
    # nodata = src.nodata
    # dx = src.transform.a
    # dy = -src.transform.e

    w = np.array([ ci, cj ]).T * (dx, dy)
    mindiff = np.float32(minslope*np.sqrt(np.sum(w*w, axis=1)))

    if out is None:
        out = np.full((height, width), nodata, dtype=np.float32)

    # if flow is None:
    #     flow = np.full((height, width), -1, dtype=np.int16)
    
    # progress = CppTermProgress(2*width*height)
    msg = 'Input is %d x %d' % (width, height)
    # progress.write(msg)
    print(msg)
    msg = 'Find boundary cells ...'
    # progress.write(msg)
    print(msg)

    with nogil:

        for i in range(height):
            for j in range(width):

                z = elevations[ i, j ]
                
                if z == nodata:

                    out[i, j] = nodata
                    # flow[i, j] = -1

                else:
                    
                    for x in range(8):
                    
                        ix = i + ci[x]
                        jx = j + cj[x]
                    
                        if not ingrid(height, width, ix, jx) or (elevations[ ix, jx ] == nodata):
                            
                            # heapq.heappush(queue, (-z, x, y))
                            entry = QueueEntry(-z, Cell(i, j))
                            queue.push(entry)
                            out[i, j] = z

                            break

                # progress.update(1)

    msg = 'Fill depressions from bottom to top ...'
    # progress.write(msg)
    print(msg)

    entry = queue.top()
    z = -entry.first
    
    msg = f'Starting from z = {z:.3f}'
    # progress.write(msg)
    print(msg)

    msg = f'Initial queue size = {queue.size()}'
    print(msg)

    # with nogil:
        
    # while not queue.empty():

    #     # z, x, y = heapq.heappop(queue)
    #     # z = out[x, y]
    #     entry = queue.top()
    #     queue.pop()

    #     z = -entry.first
    #     ij = entry.second
    #     i = ij.first
    #     j = ij.second
    #     # z = out[ i, j ]

    #     if flow[i, j] == -1:

    #         # cell is not yet labeled
            
    #         zmin = z
    #         xmin = -1

    #         for x in range(8):

    #             ix = i + ci[x]
    #             jx = j + cj[x]
                
    #             if ingrid(height, width, ix, jx):

    #                 zx = elevations[ix, jx]

    #                 if zx == nodata:
    #                     continue

    #                 if zx < zmin:
    #                     zmin = zx
    #                     xmin = x

    #             else:

    #                 # flow outside dem
    #                 xmin = x
    #                 break

    #         if xmin == -1:
    #             # no flow
    #             flow[i, j] = 0
    #         else:
    #             flow[i, j] = pow2(xmin)

    with nogil:

        while not queue.empty():

            # z, x, y = heapq.heappop(queue)
            # z = out[x, y]
            entry = queue.top()
            queue.pop()

            # z = -entry.first
            ij = entry.second
            i = ij.first
            j = ij.second
            z = out[i, j]

            for x in range(8):
                
                ix = i + ci[x]
                jx = j + cj[x]
                
                if ingrid(height, width, ix, jx):

                    zx = elevations[ix, jx]

                    if (zx != nodata) and (out[ix, jx] == nodata):

                        if zx < (z + mindiff[x]):
                            zx = z + mindiff[x]

                        out[ix, jx] = zx
                        # flow[ix, jx] = pow2(reverse_direction(x))

                        # heapq.heappush(queue, (-iz, ix, iy))
                        entry = QueueEntry(-zx, Cell(ix, jx))
                        queue.push(entry)

    msg = 'Done.'
    # progress.write(msg)
    # progress.close()
    print(msg)

    return out

@cython.boundscheck(False)
@cython.wraparound(False)
def flowdir(
    float[:, :] elevations,
    float nodata,
    short[:, :] flow = None):
    """
    Compute D8 flow direction.
    Each cell is set to flow to its neighbor with lowest z.

    Parameters
    ----------

    elevations: array-like
        Digital elevation model (DEM) raster (ndim=2).
        The input DEM should be pre-processed with a filling algorithm
        in order to remove sinks and give a gentle slop to flat areas.

    nodata: float
        no-data value in `elevations`

    flow: array-like
        Same shape as elevations, dtype=np.int16, initialized to nodata = -1

    Returns
    -------

    Flow Direction raster, dtype=np.int16, nodata = -1
    """

    cdef long width, height

    cdef long i, j, x, xmin, ix, jx
    cdef float z, zx, zmin

    height = elevations.shape[0]
    width = elevations.shape[1]

    if flow is None:
        flow = np.full((height, width), -1, dtype=np.int16)

    with nogil:

        for i in range(height):
            for j in range(width):

                z = elevations[ i, j ]
                
                if z == nodata:
                    continue

                zmin = z
                xmin = -1

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]
                    
                    if ingrid(height, width, ix, jx):

                        zx = elevations[ix, jx]

                        if zx == nodata:
                            # we don't flow to nodata cells
                            continue

                        if zx < zmin:
                            zmin = zx
                            xmin = x

                    else:

                        # flow outside dem
                        xmin = x
                        break

                if xmin == -1:
                    # no flow
                    flow[i, j] = 0
                else:
                    flow[i, j] = pow2(xmin)

    return flow