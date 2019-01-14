# -*- coding: utf-8 -*-

"""
TopoLogical Stream Burn - Cython implementation

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

ctypedef pair[unsigned char, float] TopoKey
ctypedef pair[TopoKey, Cell] TopoQueueEntry
ctypedef priority_queue[TopoQueueEntry] TopoQueue

cdef inline unsigned char reverse_direction(unsigned char x) nogil:
    """ Return D8 inverse search directions
    """
    return (x + 4) % 8

@cython.boundscheck(False)
@cython.wraparound(False)
def topo_stream_burn(
    float[:,:] elevations,
    float[:,:] streams,
    float nodata,
    float rx, float ry,
    float minslope=1e-3,
    short[:,:] out=None,
    feedback=None):
    """ Flow accumulation algorithm
        based on Lindsay (2016) `Topological Stream Burn algorithm,
        which is a variant of Wang and Liu (2006) `Fill Sinks` algorithm.
        The algorithm fills stream cells before other cells,
        starting from boundary cells with lowest z.
        When a cell is discovered, its z value is fixed
        so as z is no less than z of already disovered cells,
        with a minimal slope of `minslope`.
        Flow direction is set toward the cell from which the new cell was discovered

    Parameters
    ----------

    elevations: array-like
        Digital elevation model (DEM) raster (ndim=2)

    streams: array-like
        Rasterize stream network, same shape as `elevations`,
        with stream cells >= 1

    nodata: float
        no-data value in `elevations`    

    rx: float
        raster horizontal resolution in `elevations`

    ry: float
        raster vertical resolution in `elevations`
        (positive value)

    minslope: float
        Minimum slope to preserve between cells
        when filling up sinks.

    out: array-like
        Same shape as elevations, dtype=np.int16, initialized to -1

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback

    Returns
    -------

    D8 Flow Direction raster, dtype:np.int16, nodata=-1

    Notes
    -----

    [1] Lindsay, J. B. (2016).
        The Practice of DEM Stream Burning Revisited.
        Earth Surface Processes and Landforms, 41(5), 658‑668. 
        https://doi.org/10.1002/esp.3888

    [2] Wang, L. & H. Liu (2006)
        An efficient method for identifying and filling surface depressions
        in digital elevation models.
        International Journal of Geographical Information Science,
        Vol. 20, No. 2: 193-213.

    [3] SAGA C++ Implementation
        https://github.com/saga-gis/saga-gis/blob/1b54363/saga-gis/src/tools/terrain_analysis/ta_preprocessor/FillSinks_WL_XXL.cpp
        GPL Licensed
    """

    cdef long width, height
    cdef float dx, dy, z, zx
    cdef np.ndarray[double, ndim=2] w
    cdef np.ndarray[float] mindiff
    cdef long i, j, ix, jx, x, ncells, current
    cdef unsigned char instream, instreamx

    cdef Cell cell
    cdef TopoKey key
    cdef TopoQueueEntry entry
    cdef TopoQueue queue

    cdef float total
    cdef int progress0, progress1

    if feedback is None:
        feedback = SilentFeedback()

    height = elevations.shape[0]
    width = elevations.shape[1]

    w = np.array([ ci, cj ]).T * (rx, ry)
    mindiff = np.float32(minslope*np.sqrt(np.sum(w*w, axis=1)))

    if out is None:
        out = np.full((height, width), -1, dtype=np.int16)

    # progress = TermProgressBar(2*width*height)
    feedback.setProgressText('Input is %d x %d' % (width, height))

    total = 100.0 / (height*width)
    progress0 = progress1 = 0

    # with nogil:

    for i in range(height):
        for j in range(width):

            z = elevations[i, j]
            instream = 1 if streams[i, j] > 0 else 0

            if z != nodata:

                ncells += 1

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if not ingrid(height, width, ix, jx) or (elevations[ix, jx] == nodata):

                        # out[ i, j ] = z
                        # heappush(queue, (instream, z, i, j))
                        cell = Cell(i, j)
                        key = TopoKey(instream, -z)
                        entry = TopoQueueEntry(key, cell)
                        queue.push(entry)

                        break

        progress1 = int((i*width+j)*total)
        if progress1 > progress0:
            feedback.setProgress(progress1)
            progress0 = progress1
            if feedback.isCanceled():
                break

    feedback.setProgressText('Fill depressions from bottom to top ...')
    total = 100.0 / ncells
    progress0 = progress1 = 0
    current = 0

    while not queue.empty():

        # instream, z, i, j = heappop(queue)
        entry = queue.top()
        queue.pop()
        key = entry.first
        cell = entry.second
        instream = key.first
        z = -key.second
        i = cell.first
        j = cell.second

        if out[i, j] == -1:
            out[i, j] = 0

        for x in range(8):

            ix = i + ci[x]
            jx = j + cj[x]

            if ingrid(height, width, ix, jx):

                zx = elevations[ix, jx]
                instreamx = 1 if streams[ix, jx] > 0 else 0

                if (zx != nodata) and (out[ix, jx] == -1):

                    if zx < (z + mindiff[x]):
                        zx = z + mindiff[x]

                    out[ix, jx] = pow2(reverse_direction(x))
                    # heappush(queue, (instreamx, zx, ix, jx))
                    cell = Cell(ix, jx)
                    key = TopoKey(instreamx, -zx)
                    entry = TopoQueueEntry(key, cell)
                    queue.push(entry)

        current += 1
        progress1 = int(current*total)
        if progress1 > progress0:
            feedback.setProgress(progress1)
            progress0 = progress1
            if feedback.isCanceled():
                break

    return out
