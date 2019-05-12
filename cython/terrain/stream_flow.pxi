# coding: utf-8

@cython.boundscheck(False)
@cython.wraparound(False)
def stream_flow(
    float[:, :] elevations,
    float[:,:] streams,
    float nodata,
    short[:, :] flow = None,
    feedback=None):
    """
    Flow direction from elevation data.

    Assign flow direction toward the lower neighbouring cell.

    Parameters
    ----------

    elevations: array-like, ndims=2, dtype=float32
        Elevation raster

    streams: array-like
        Rasterize stream network, same shape as `elevations`,
        with stream cells >= 1

    nodata: float
        No data value for elevation

    Returns
    -------

    int16 D8 Flow Direction NumPy array, nodata = -1

    """

    cdef:

        long width, height
        long i, j, x, xmin, sxmin, ix, jx
        float z, zx, zmin, smin, szmin

        Cell c
        deque[Cell] unresolved
        bint resolved, is_sink

        float total
        int progress0, progress1

    if feedback is None:
        feedback = SilentFeedback()

    height = elevations.shape[0]
    width = elevations.shape[1]

    if flow is None:
        flow = np.full((height, width), -1, dtype=np.int16)

    seen = np.zeros((height, width), dtype=np.uint8)

    total = 100.0 / (height*width)

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            z = elevations[i, j]
            
            if z == nodata:
                continue

            if streams[i, j] > 0:

                zmin = szmin = z
                xmin = sxmin = -1
                smin = streams[i, j]

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if not ingrid(height, width, ix, jx):
                        continue

                    if streams[ix, jx] <= 0:
                        continue

                    zx = elevations[ix, jx]

                    if streams[ix, jx] == streams[i, j] and zx < zmin:
                        zmin = zx
                        xmin = x

                    if streams[ix, jx] < smin:
                        smin = streams[ix, jx]
                        szmin = zx
                        sxmin = x
                    elif streams[ix, jx] == smin and zx < szmin:
                        szmin = zx
                        sxmin = x

                if xmin == -1:
                    if sxmin == -1:
                        # unresolved flow
                        # flow[i, j] = 0
                        unresolved.push_back(Cell(i, j))
                    else:
                        flow[i, j] = pow2(sxmin)
                else:
                    flow[i, j] = pow2(xmin)

            else:

                zmin = z
                xmin = -1

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]
                    
                    if not ingrid(height, width, ix, jx):
                        continue

                    zx = elevations[ix, jx]

                    if zx == nodata:
                        continue

                    if zx < zmin:
                        zmin = zx
                        xmin = x

                if xmin == -1:
                    # no flow
                    flow[i, j] = 0
                else:
                    flow[i, j] = pow2(xmin)

        progress1 = int(((i+1)*width)*total)
        if progress1 > progress0:
            feedback.setProgress(progress1)
            progress0 = progress1

    while not unresolved.empty():

        if feedback.isCanceled():
            break

        c = unresolved.front()
        unresolved.pop_front()
        i = c.first
        j = c.second

        if flow[i, j] != -1:
            # The cell has been resolved meanwhile
            continue

        is_sink = True
        resolved = False

        z = elevations[i, j]
        smin = streams[i, j]
        zmin = z
        xmin = -1

        for x in range(8):

            # Lookup for an adjacent resolved stream cells
            # with same elevation and compatible stream ID

            ix = i + ci[x]
            jx = j + cj[x]
            
            if not ingrid(height, width, ix, jx):
                continue

            zx = elevations[ix, jx]

            if zx == nodata:
                continue

            if streams[ix, jx] <= smin:

                if flow[ix, jx] != -1:
                    
                    # We found an adjacent stream cell
                    # and it has been resolved.
                    # Flow toward this cell and we are done.

                    flow[i, j] = pow2(x)
                    is_sink = False
                    resolved = True
                    break

                if zx <= z:
                    
                    # There is an adjacent stream cell with same elevation
                    # but it has not yet been resolved
                    is_sink = False

            if zx < zmin:
                zmin = zx
                xmin = x

        if is_sink:

            # We found no adjacent stream cell
            # with same elevation or lower.
            # We may be at an outlet of the stream network.
            # Resolve cell as an ordinary cell

            if xmin == -1:
                # no flow
                flow[i, j] = 0
            else:
                flow[i, j] = pow2(xmin)

            resolved = True

        if resolved:

            # Push unresolved neighbors to the queue

            for x in range(8):

                ix = i + ci[x]
                jx = j + cj[x]
                
                if not ingrid(height, width, ix, jx):
                    continue

                if elevations[ix, jx] == nodata:
                    continue

                if streams[ix, jx] > 0 and flow[ix, jx] == -1:
                    unresolved.push_back(Cell(ix, jx))

    return np.int16(flow)