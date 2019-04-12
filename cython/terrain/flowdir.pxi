# coding: utf-8

@cython.boundscheck(False)
@cython.wraparound(False)
def flowdir(
    float[:, :] elevations,
    float nodata,
    short[:, :] flow = None):
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

    return np.int16(flow)