import numpy as np
from heapq import heapify, heappop, heappush

# D8 directions in 3x3 neighborhood

d8_directions = np.power(2, np.array([7, 0, 1, 6, 0, 2, 5, 4, 3], dtype=np.uint8))
d8_directions[5] = 0

# D8 search directions, clockwise starting from North
#       0   1   2   3   4   5   6   7
#       N  NE   E  SE   S  SW   W  NW

ci = [-1, -1,  0,  1,  1,  1,  0, -1]
cj = [ 0,  1,  1,  1,  0, -1, -1, -1]

# Flow direction value of upward cells
# in each search direction,
# e.g. cell north (search index 0) of cell x is connected to cell x
#      if its flow direction is 2^4 (southward)

upward = np.power(2, np.array([4,  5,  6,  7,  0,  1,  2,  3], dtype=np.uint8))

def ingrid(data, i, j):
    """ Tests if cell (i, j) is within the range of data

    Parameters
    ----------

    data: array-like, ndim=2
        Input raster

    i: int
        Row index

    j: int
        Column index

    Returns
    -------

    True if coordinates (i, j) fall within data, False otherwise.
    """

    height = data.shape[0]
    width = data.shape[1]

    return (i >= 0) and (i < height) and (j >= 0) and (j < width)

def reverse_direction(x):
    """ Return D8 inverse search directions
    """

    return (x + 4) % 8

def topo_stream_burn(elevations, streams, nodata, rx, ry, minslope=1e-3, feedback=None, out=None):
    """
    Flow accumulation

    Implementation of Lindsay (2016) `Topological Stream Burn algorithm,
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

    feedback: QgsProcessingFeedback-like object
        or None to disable feedback

    out: array-like
        Same shape as elevations, dtype=np.int8, initialized to -1

    Returns
    -------

    D8 Flow Direction raster, dtype:np.int8, nodata=-1

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
    height = elevations.shape[0]
    width = elevations.shape[1]

    w = np.array([ci, cj]).T * (rx, ry)
    mindiff = np.float32(minslope*np.sqrt(np.sum(w*w, axis=1)))

    if out is None:
        out = np.full(elevations.shape, -1, dtype=np.int8)

    # progress = TermProgressBar(2*width*height)
    # progress.write('Input is %d x %d' % (width, height))

    feedback.setProgressText('Find boundary cells ...')

    # We use a heap queue to sort cells
    # from lower z to higher z.
    # Remember python's heapq is a min-heap.
    queue = list()
    total = 100.0 / (height*width)

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            z = elevations[i, j]
            instream = 0 if streams[i, j] > 0 else 1

            if z != nodata:

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if not ingrid(elevations, ix, jx) or (elevations[ix, jx] == nodata):

                        # out[ i, j ] = z
                        heappush(queue, (instream, z, i, j))

                        break

        feedback.setProgress(int((i*width)*total))

    feedback.setProgressText('Fill depressions from bottom to top ...')

    instream, z, i, j = queue[0]
    feedback.setProgressText('Starting from z = %f' % z)
    current = 0

    while queue:

        if feedback.isCanceled():
            break

        instream, z, i, j = heappop(queue)
        if out[i, j] == -1:
            out[i, j] = 0

        for x in range(8):

            ix = i + ci[x]
            jx = j + cj[x]

            if ingrid(elevations, ix, jx):

                zx = elevations[ix, jx]
                instreamx = 0 if streams[ix, jx] > 0 else 1

                if (zx != nodata) and (out[ix, jx] == -1):

                    if zx < (z + mindiff[x]):
                        zx = z + mindiff[x]

                    out[ix, jx] = pow(2, reverse_direction(x))
                    heappush(queue, (instreamx, zx, ix, jx))

        current += 1
        feedback.setProgress(int(current*total))

    return out
