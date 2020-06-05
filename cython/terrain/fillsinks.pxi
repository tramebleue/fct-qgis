# -*- coding: utf-8 -*-

"""
Priority Flood Depression Filling - Flow Direction

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
        float zdelta=0,
        float[:, :] out=None,
        short[:, :] flow=None,
        feedback=None):
    """
    Fill sinks of digital elevation model (DEM),
    based on the algorithm of Wang & Liu (2006).

    Parameters
    ----------

    elevations: array-like
        Digital elevation model (DEM) raster (ndim=2)

    nodata: float
        no-data value in `elevations`    

    zdelta: float
        Minimum z delta to preserve between cells
        when filling up sinks.

    out: array-like
        Same shape and dtype as elevations, initialized to nodata
        It is safe to pass `out = elevations` to save some memory
        when processing large raster ?

    flow: array-like
        Optional flow direction output
        Same shape as elevations, dtype int16, initialized to -1

    feedback: QgsFeedback-like object

    Returns
    -------

    Depression filled elevation raster.

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

    cdef:

        long width, height
        long i, j, x, xmin, ix, jx
        float z, zx, zmin

        Cell ij
        QueueEntry entry
        CellQueue queue
        unsigned char[:, :] settled

        bint flow_output = False

        short FLOW_NODATA = -1
        short NO_FLOW = 0
        
        double total
        int progress0, progress1

    height = elevations.shape[0]
    width = elevations.shape[1]
    total = 100.0 / (height*width)

    if out is None:
        out = np.full((height, width), nodata, dtype=np.float32)

    if flow is not None:
        flow_output = True
        flow[:, :] = FLOW_NODATA

    # TODO
    # test for congruent dimensions among elevations, out and flow

    settled = np.zeros((height, width), dtype=np.uint8)

    if feedback is None:
        feedback = SilentFeedback()

    # Find boundary cells
    
    feedback.setProgressText('Input is %d x %d' % (width, height))
    feedback.setProgressText('Find boundary cells ...')

    for i in range(height):
        for j in range(width):

            z = elevations[i, j]
            
            if z != nodata:
                
                for x in range(8):
                
                    ix = i + ci[x]
                    jx = j + cj[x]
                
                    if not ingrid(height, width, ix, jx) or (elevations[ix, jx] == nodata):
                        
                        entry = QueueEntry(-z, Cell(i, j))
                        queue.push(entry)
                        # visited[i, j] = 1
                        out[i, j] = z

                        break

        if feedback.isCanceled():
            break

        feedback.setProgress(int(total * i * width))

    if feedback.isCanceled():
        return np.asarray(out)

    # Priority flood from lowest to highest terrain

    feedback.setProgressText('Fill depressions from bottom to top ...')
    progress0 = progress1 = 0
    current = 0

    while not queue.empty():

        entry = queue.top()
        queue.pop()

        z = -entry.first
        ij = entry.second
        i = ij.first
        j = ij.second
        # z = elevations[i, j]

        if settled[i, j] == 1:
            # already settled
            continue

        out[i, j] = z
        settled[i, j] = 1

        # Calculate flow direction to lowest neighbor

        if flow_output:

            zmin = z
            xmin = -1

            for x in range(8):

                ix = i + ci[x]
                jx = j + cj[x]
                
                if ingrid(height, width, ix, jx):

                    # consider only settled cells,
                    # other cells either have elevation >= z
                    # or are sinks

                    zx = out[ix, jx]

                    if (zx != nodata) and (settled[ix, jx] == 1):

                        if zx < zmin:
                            zmin = zx
                            xmin = x

            if xmin == -1:
                # we found no neighbor cell having z < zmin
                # no flow
                flow[i, j] = NO_FLOW
            else:
                flow[i, j] = pow2(xmin)

        # Discover neighbor cells

        for x in range(8):
            
            ix = i + ci[x]
            jx = j + cj[x]
            
            if ingrid(height, width, ix, jx):

                zx = elevations[ix, jx]

                if (zx != nodata) and (settled[ix, jx] == 0):

                    if zx < z + zdelta:
                        zx = z + zdelta

                    if (out[ix, jx] == nodata) or (out[ix, jx] > zx):

                        # out[ix, jx] == nodata : not yet discovered
                        # out[ix, jx] > zx : this alternative path yields a lower z for cell (ix, jx)
                        #     though we should always discover cells from the lowest neighbor cell

                        out[ix, jx] = zx
                        entry = QueueEntry(-zx, Cell(ix, jx))
                        queue.push(entry)

        current += 1
        progress1 = int(current*total)
        
        if progress1 > progress0:

            if feedback.isCanceled():
                break
        
            feedback.setProgress(progress1)
            progress0 = progress1

    feedback.setProgress(100)

    return np.asarray(out)