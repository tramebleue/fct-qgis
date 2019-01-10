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
upward[5] = 0

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

def topo_stream_burn(elevations, streams, nodata, rx, ry, out=None, minslope=1e-3, feedback=None):
    """ Fill sinks of digital elevation model (DEM),
        based on the algorithm of Wang & Liu (2006).

    Parameters
    ----------

    elevations: array-like
        Digital elevation model (DEM) raster (ndim=2)

    streams: array-like
        Digital elevation model (DEM) raster (ndim=2)

    nodata: float
        No-data value in elevations

    rx: float
        Cell resolution in x direction

    ry: float
        Cell resolution in y direction

    out: array-like
        Same shape and dtype as elevations, initialized to nodata

    minslope: float
        Minimum slope to preserve between cells
        when filling up sinks.

    Returns
    -------

    D8 Flow Direction raster

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

    height = elevations.shape[0]
    width = elevations.shape[1]

    w = np.array([ci, cj]).T * (rx, ry)
    mindiff = np.float32(minslope*np.sqrt(np.sum(w*w, axis=1)))

    if out is None:
        out = np.full(elevations.shape, -1, dtype=np.float32)

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
