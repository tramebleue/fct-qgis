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

ctypedef pair[int, Label] WatershedLabel
ctypedef pair[WatershedLabel, WatershedLabel] WatershedPair
ctypedef map[WatershedPair, float] WatershedGraph

cdef enum EdgeSide:
    TOP = 0
    RIGHT = 1
    BOTTOM = 2
    LEFT = 3

@cython.boundscheck(False)
cdef void connect(
    WatershedGraph& graph,
    WatershedLabel l1,
    float z1,
    WatershedLabel l2,
    float z2) nogil:

    cdef:
        float over_z
        WatershedPair p

    if l1 > l2:
        l1, l2 = l2, l1

    p = WatershedPair(l1, l2)
    over_z = max[float](z1, z2)

    if graph.count(p) == 0:
        graph[p] = over_z
    else:
        if over_z < graph[p]:
            graph[p] = over_z
        

@cython.boundscheck(False)
cdef void connect_exterior_edge(
    WatershedGraph& graph,
    float[:, :] elevations,
    float nodata,
    Label[:, :] labels,
    int tile_id,
    int edge_side):

    cdef:

        int k, width = elevations.shape[1]
        float z1, z2
        WatershedLabel l1, l2

    with nogil:
        for k in range(width):
            z1 = elevations[edge_side, k]
            if z1 == nodata:
                continue
            l1 = WatershedLabel(tile_id, labels[edge_side, k])
            l2 = WatershedLabel(-1, 1)
            z2 = nodata
            connect(graph, l1, z1, l2, z2)

@cython.boundscheck(False)
cdef void connect_edge(
    WatershedGraph& graph,
    float[:, :] elevations,
    float nodata,
    Label[:, :] labels,
    int tile_id,
    float[:, :] neighbor_elevations,
    Label[:, :] neighbor_labels,
    int neighbor_id,
    int edge_side):

    cdef:

        int k, s, width = elevations.shape[1], neighbor_side = (edge_side + 2) % 4
        float z1, z2
        WatershedLabel l1, l2

    with nogil:
        for k in range(width):
            
            z1 = elevations[edge_side, k]
            
            if z1 == nodata:
                l1 = WatershedLabel(-1, 1)
            else:
                l1 = WatershedLabel(tile_id, labels[edge_side, k])
            
            for s in range(-1, 2):
                if k+s < 0 or k+s == elevations.shape[1]:
                    continue
                
                z2 = neighbor_elevations[neighbor_side, -(k+s)-1]
                if z2 == nodata:
                    l2 = WatershedLabel(-1, 1)
                else:
                    l2 = WatershedLabel(neighbor_id, neighbor_labels[neighbor_side, -(k+s)-1])
                
                connect(graph, l1, z1, l2, z2)

cdef void connect_corner(
    WatershedGraph& graph,
    float[:, :] elevations,
    float nodata,
    Label[:, :] labels,
    int tile_id,
    float[:, :] corner_elevations,
    Label[:, :] corner_labels,
    int corner_id,):

    cdef:

        float z1, z2
        WatershedLabel l1, l2

    z1 = elevations[0, 0]
    if z1 == nodata:
        l1 = WatershedLabel(-1, 1)
    else:
        l1 = WatershedLabel(tile_id, labels[0, 0])
    
    z2 = corner_elevations[2, 0]
    if z2 == nodata:
        l2 = WatershedLabel(-1, 1)
    else:
        l2 = WatershedLabel(corner_id, corner_labels[2, 0])

    connect(graph, l1, z1, l2, z2)

def connect_tile(int row, int col, float nodata, tilematrix, tiledatafn):
    """
    Return connection graph to neighbor tiles.
    """

    cdef:

        int tile_id, neighbor_id, height, width
        float z1, z2

        float[:, :] elevations
        Label[:, :] labels

        float[:, :] neighbor_elevations
        Label[:, :] neighbor_labels

        WatershedGraph graph
        WatershedLabel l1, l2
        WatershedPair p

    height = tilematrix.shape[0]
    width = tilematrix.shape[1]
    tile = tilematrix[row, col]
    tile_id = row*height+col
    data = np.load(tiledatafn(tile))
    elevations = data['z']
    labels = data['labels']

    for link, z in data['graph']:
        l1 = WatershedLabel(tile_id, link[0])
        l2 = WatershedLabel(tile_id, link[1])
        p = WatershedPair(l1, l2)
        graph[p] = z

    # for e in range(4):
    #     for k in range(elevations.shape[1]-1):

    #         z1 = elevations[e, k]
    #         l1 = (tile_id, labels[e, k])
    #         z2 = elevations[e, k+1]
    #         l2 = (tile_id, labels[e, k+1])
    #         if z1 == nodata or z2 == nodata:
    #             continue
    #         connect(l1, z1, l2, z2)

    if row == 0:

        connect_exterior_edge(
            graph,
            elevations, nodata, labels, tile_id,
            EdgeSide.TOP)

    else:

        # match top edge to bottom edge of row-1 cell
        neighbor_tile = tilematrix[row-1, col]
        neighbor_id = (row-1)*height+col
        neighbor_data = np.load(tiledatafn(neighbor_tile))
        neighbor_elevations = neighbor_data['z']
        neighbor_labels = neighbor_data['labels']

        connect_edge(
            graph,
            elevations, nodata, labels, tile_id,
            neighbor_elevations, neighbor_labels, neighbor_id,
            EdgeSide.TOP)

        if col > 0:

            # match top-left corner with bottom-right corner of (row-1, cell-1) cell
            corner_tile = tilematrix[row-1, col-1]
            neighbor_id = (row-1)*height+col-1
            neighbor_data = np.load(tiledatafn(corner_tile))
            neighbor_elevations = neighbor_data['z']
            neighbor_labels = neighbor_data['labels']

            connect_corner(
                graph,
                elevations, nodata, labels, tile_id,
                neighbor_elevations, neighbor_labels, neighbor_id)

    if row == height-1:

        connect_exterior_edge(
            graph,
            elevations, nodata, labels, tile_id,
            EdgeSide.BOTTOM)

    if col == 0:

        connect_exterior_edge(
            graph,
            elevations, nodata, labels, tile_id,
            EdgeSide.LEFT)

    else:

        # match left edge to right edge of col-1 cell
        neighbor_tile = tilematrix[row, col-1]
        neighbor_id = row*height+col-1
        neighbor_data = np.load(tiledatafn(neighbor_tile))
        neighbor_elevations = neighbor_data['z']
        neighbor_labels = neighbor_data['labels']

        connect_edge(
            graph,
            elevations, nodata, labels, tile_id,
            neighbor_elevations, neighbor_labels, neighbor_id,
            EdgeSide.LEFT)

    if col == width-1:

        connect_exterior_edge(
            graph,
            elevations, nodata, labels, tile_id,
            EdgeSide.RIGHT)

    return graph