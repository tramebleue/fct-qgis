# -*- coding: utf-8 -*-

"""
Watershed Labeling with Depression Filling

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

ctypedef unsigned int Label
ctypedef pair[Label, Label] LabelPair
ctypedef map[LabelPair, float] SpilloverGraph

@cython.boundscheck(False)
@cython.wraparound(False)
cdef void grow_pit_region(
    float[:, :] elevations,
    float nodata,
    Label[:, :] labels,
    long height,
    long width,
    Label region_label,
    CellStack& queue,
    CellStack& slope) nogil:

    cdef:

        Cell c
        long i, j, ix, jx, x
        float z

    while not queue.empty():

        c = queue.top()
        queue.pop()

        i = c.first
        j = c.second
        z = elevations[i, j]

        for x in range(8):
                    
            ix = i + ci[x]
            jx = j + cj[x]

            if not ingrid(height, width, ix, jx) or elevations[ix, jx] == nodata:
                continue

            if labels[ix, jx] > 0:
                continue

            labels[ix, jx] = region_label

            if elevations[ix, jx] <= z:

                elevations[ix, jx] = z
                queue.push(Cell(ix, jx))

            else:

                slope.push(Cell(ix, jx))

@cython.boundscheck(False)
@cython.wraparound(False)
cdef void grow_slope_region(
    float[:, :] elevations,
    float nodata,
    Label[:, :] labels,
    long height,
    long width,
    Label region_label,
    CellStack& queue,
    CellQueue& priority) nogil:

    cdef:

        bint processed
        Cell c
        long i, j, ix, jx, x
        float z

    while not queue.empty():

        c = queue.top()
        queue.pop()

        i = c.first
        j = c.second
        processed = False
        z = elevations[i, j]

        for x in range(8):
                    
            ix = i + ci[x]
            jx = j + cj[x]

            if not ingrid(height, width, ix, jx) or elevations[ix, jx] == nodata:
                continue

            if labels[ix, jx] > 0:
                continue

            if elevations[ix, jx] > z:

                labels[ix, jx] = region_label
                queue.push(Cell(ix, jx))

            elif not processed:

                processed = True
                priority.push(QueueEntry(-z, c))

@cython.boundscheck(False)
@cython.wraparound(False)
def watershed_labels(
        float[:, :] elevations,
        float nodata,
        # float dx, float dy,
        # float minslope=1e-3,
        # float[:, :] out = None,
        Label[:, :] labels = None):
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

    cdef:

        long width, height
        long i, j, x, xmin, ix, jx
        float z, zx, zmin, over_z
        Label label, other_label, next_label = 1

        Cell c
        QueueEntry entry
        CellQueue priority
        CellStack pit
        CellStack slope
        SpilloverGraph graph
        LabelPair edge

        # np.ndarray[double, ndim=2] w
        # np.ndarray[float] mindiff

    height = elevations.shape[0]
    width = elevations.shape[1]

    # w = np.array([ ci, cj ]).T * (dx, dy)
    # mindiff = np.float32(minslope*np.sqrt(np.sum(w*w, axis=1)))

    if labels is None:
        labels = np.zeros((height, width), dtype=np.uint32)
    
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

                z = elevations[i, j]
                
                if z != nodata:
                    
                    for x in range(8):
                    
                        ix = i + ci[x]
                        jx = j + cj[x]
                    
                        if not ingrid(height, width, ix, jx) or (elevations[ix, jx] == nodata):
                            
                            # heapq.heappush(queue, (-z, x, y))
                            entry = QueueEntry(-z, Cell(i, j))
                            priority.push(entry)

                            break

                # progress.update(1)

    msg = 'Fill depressions from bottom to top ...'
    # progress.write(msg)
    print(msg)

    entry = priority.top()
    z = -entry.first
    
    msg = f'Starting from z = {z:.3f}'
    # progress.write(msg)
    print(msg)

    msg = f'Initial queue size = {priority.size()}'
    print(msg)

    with nogil:

        while not priority.empty():

            entry = priority.top()
            priority.pop()

            z = -entry.first
            c = entry.second
            i = c.first
            j = c.second

            label = labels[i, j]

            if label == 0:

                zmin = z

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if not ingrid(height, width, ix, jx) or elevations[ix, jx] == nodata:
                        continue

                    if labels[ix, jx] > 1 and elevations[ix, jx] < zmin:

                        zmin = elevations[ix, jx]
                        label = labels[ix, jx]

                if label == 0:

                    label = next_label
                    next_label += 1
                    labels[i, j] = label

                else:

                    labels[i, j] = label

            for x in range(8):

                ix = i + ci[x]
                jx = j + cj[x]

                if not ingrid(height, width, ix, jx):
                    continue

                # FIXME when watershed connects to nodata region

                if elevations[ix, jx] == nodata:

                    other_label = 0
                    zx = nodata
                    edge = LabelPair(other_label, label)
                    over_z = z

                    if graph.count(edge) == 0:
                        graph[edge] = over_z
                    elif over_z < graph[edge]:
                        graph[edge] = over_z


                else:

                    other_label = labels[ix, jx]
                    zx = elevations[ix, jx]

                    if other_label > 0:

                        if other_label != label:

                            if label > other_label:
                                # swap(label, other_label)
                                label, other_label = other_label, label
                            
                            edge = LabelPair(label, other_label)
                            over_z = max[float](z, zx)
                            
                            if graph.count(edge) == 0:
                                graph[edge] = over_z
                            elif over_z < graph[edge]:
                                graph[edge] = over_z
                        
                        continue

                    labels[ix, jx] = label
                
                    if zx < z:

                        elevations[ix, jx] = z
                        pit.push(Cell(ix, jx))
                        grow_pit_region(elevations, nodata, labels, height, width, label, pit, slope)

                    else:

                        slope.push(Cell(ix, jx))

            grow_slope_region(elevations, nodata, labels, height, width, label, slope, priority)

    msg = f'Found {next_label-1} watersheds.'
    print(msg)

    msg = 'Done.'
    print(msg)

    return np.asarray(labels), graph

@cython.boundscheck(False)
@cython.wraparound(False)
cdef void grow_flat_region(
    float[:, :] flats,
    float nodata,
    Label[:, :] labels,
    long height,
    long width,
    Label region_label,
    CellStack& queue) nogil:

    cdef:

        Cell c
        long i, j, ix, jx, x

    while not queue.empty():

        c = queue.top()
        queue.pop()

        i = c.first
        j = c.second

        for x in range(8):
                    
            ix = i + ci[x]
            jx = j + cj[x]

            if not ingrid(height, width, ix, jx) or flats[ix, jx] == nodata:
                continue

            if labels[ix, jx] > 0:
                continue

            labels[ix, jx] = region_label

            if flats[ix, jx] > 0:

                queue.push(Cell(ix, jx))

def flat_labels(
        float[:, :] flats,
        float nodata,
        # float dx, float dy,
        # float minslope=1e-3,
        # float[:, :] out = None,
        Label[:, :] labels = None):

    cdef:

        long height = flats.shape[0], width = flats.shape[1]
        long i, j
        Label next_label = 1
        CellStack pit

    if labels is None:
        labels = np.zeros((height, width), dtype=np.uint32)

    for i in range(height):
        for j in range(width):

            if flats[i, j] == nodata:
                continue

            if flats[i, j] > 0 and labels[i, j] == 0:

                label = next_label
                next_label += 1
                labels[i, j] = label

                pit.push(Cell(i, j))
                grow_flat_region(flats, nodata, labels, height, width, label, pit)

    return np.asarray(labels)

def flat_boxes(Label[:, :] labels):

    cdef:

        long height = labels.shape[0], width = labels.shape[1]
        long i, j
        Label label
        map[Label, long] mini, minj, maxi, maxj, count

    for i in range(height):
        for j in range(width):

            label = labels[i, j]

            if label > 0:

                if mini.count(label) == 0:

                    mini[label] = i
                    minj[label] = j
                    maxi[label] = i
                    maxj[label] = j
                    count[label] = 1

                else:

                    mini[label] = min[long](i, mini[label])
                    minj[label] = min[long](j, minj[label])
                    maxi[label] = max[long](i, maxi[label])
                    maxj[label] = max[long](j, maxj[label])
                    count[label] += 1

    return {l: (mini[l], minj[l], maxi[l], maxj[l], count[l]) for l in dict(mini)}


