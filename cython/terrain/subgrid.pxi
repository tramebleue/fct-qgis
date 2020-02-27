# -*- coding: utf-8 -*-

"""
Subgrid Topography

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

ctypedef pair[Cell, Cell] GridExtent

ctypedef pair[Cell, ContributingArea] Outlet

@cython.boundscheck(False)
@cython.wraparound(False)
cdef GridExtent grid_extent(float[:, :] geometry, GeoTransform transform) nogil:

    cdef:

        Point coordinate
        Cell pixel
        long length = geometry.shape[0], k
        long mini = - 1, minj = -1, maxi = -1, maxj = -1

    for k in range(length):

        coordinate = Point(geometry[k, 0], geometry[k, 1])
        pixel = pointtopixel(coordinate, transform)

        if pixel.first < mini or mini == -1:
            mini = pixel.first
        if pixel.first > maxi:
            maxi = pixel.first
        if pixel.second < minj or minj == -1:
            minj = pixel.second
        if pixel.second > maxj:
            maxj = pixel.second

    return GridExtent(Cell(mini, minj), Cell(maxi, maxj))

cdef inline float cross(float ax, float ay, float bx, float by, float cx, float cy) nogil:

    return (bx - ax)*(cy - ay) - (by - ay)*(cx - ax)

@cython.boundscheck(False)
@cython.wraparound(False)
cdef bint point_in_ring(Point p, float[:, :] ring) nogil:
    """
    Javascript implementation :

    function pointInRing(point, ring) {

        var nodes = ring.length;

        var node = function(i) {
            return {
              lon: ring[i][0],
              lat: ring[i][1]
            };
        };

        var cross = function(a, b, c) {
            var bx = b.lon - a.lon;
            var by = b.lat - a.lat;
            var cx = c.lon - a.lon;
            var cy = c.lat - a.lat;
            return (bx * cy - by * cx);
        };

        var p = {
            lon: point.coordinates[0],
            lat: point.coordinates[1]
        };

        var windingNumber = 0;

        for (var i=0; i<nodes-1; i++) {
            var e1 = node(i);
            var e2 = node(i+1);
            if (e1.lat <= p.lat) {
              if (e2.lat > p.lat) {
                if (cross(e1, e2, p) > 0) { // p left of edge (e1, e2)
                  windingNumber++;
                }
              }
            } else {
              if (e2.lat <= p.lat) {
                if (cross(e1, e2, p) < 0) { // p right of edge (e1, e2)
                  windingNumber--;
                }
              }
            }
        }

        return (windingNumber !== 0);

    }

    """

    # cdef:

    #     long windingNumber = 0, length = ring.shape[0], i
    #     float x, y, x1, x2, y1, y2

    # x = p.first
    # y = p.second

    # for i in range(length-1):

    #     x1 = ring[i, 0]
    #     y1 = ring[i, 1]
    #     x2 = ring[i+1, 0]
    #     y2 = ring[i+1, 1]

    #     if y1 <= y:
    #         if y2 > y:
    #             if cross(x1, y1, x2, y2, x, y) > 0:
    #                 windingNumber += 1
    #     else:
    #         if y2 <= y:
    #             if cross(x1, y1, x2, y2, x, y) < 0:
    #                 windingNumber -= 1

    # return (windingNumber != 0)

    # int pnpoly(int nvert, float *vertx, float *verty, float testx, float testy)
    # {
    #   int i, j, c = 0;
    #   for (i = 0, j = nvert-1; i < nvert; j = i++) {
    #     if ( ((verty[i]>testy) != (verty[j]>testy)) &&
    #      (testx < (vertx[j]-vertx[i]) * (testy-verty[i]) / (verty[j]-verty[i]) + vertx[i]) )
    #        c = !c;
    #   }
    #   return c;
    # }

    cdef:

        int i, length = ring.shape[0]
        bint c = False
        float x, y, x1, x2, y1, y2

    x = p.first
    y = p.second

    for i in range(length-1):

        x1 = ring[i, 0]
        y1 = ring[i, 1]
        x2 = ring[i+1, 0]
        y2 = ring[i+1, 1]

        if ((y1 > y) != (y2 > y)) and (x < (x2-x1)*(y-y1) / (y2-y1) + x1):
            c = not c

    return c


@cython.boundscheck(False)
@cython.wraparound(False)
cdef ContributingArea local_contributive_area(Cell pixel, short[:, :] flow, unsigned char[:, :] mask):

    cdef:

        long height = flow.shape[0], width = flow.shape[1]
        long i, j, ix, jx
        Cell current
        CellStack queue
        ContributingArea lca = 0
        int x

    queue.push(pixel)

    while not queue.empty():

        current = queue.top()
        queue.pop()

        i = current.first
        j = current.second

        for x in range(8):

            ix =  i + ci[x]
            jx =  j + cj[x]

            if ingrid(height, width, ix, jx) and mask[ix, jx] and flow[ix, jx] == upward[x] :

                lca += 1
                queue.push(Cell(ix, jx))

    return lca

@cython.boundscheck(False)
@cython.wraparound(False)
cdef Outlet subgrid_outlet(float[:, :] geometry, short[:, :] flow, ContributingArea[:, :] acc, unsigned char[:, :] mask, GeoTransform transform):
    """
    DOCME
    """

    cdef:

        GridExtent extent
        long height = flow.shape[0], width = flow.shape[1]
        long i, j, mini, minj, maxi, maxj
        Point p
        Cell pixel, other_pixel
        QueueEntry entry
        CellQueue queue
        ContributingArea area, other_area

    extent = grid_extent(geometry, transform)
    mini = extent.first.first
    minj = extent.first.second
    maxi = extent.second.first
    maxj = extent.second.second

    for i in range(mini, maxi+1):
        for j in range(minj, maxj+1):

            if not ingrid(height, width, i, j):
                continue

            pixel = Cell(i, j)
            p = pixeltopoint(pixel, transform)

            if flow[i, j] != -1 and point_in_ring(p, geometry):

                mask[i, j] = True
                area = acc[i, j]
                entry = QueueEntry(area, pixel)
                queue.push(entry)

    if queue.empty():
        
        pixel = Cell(-1, -1)
        area = 0
        return Outlet(pixel, area)

    entry = queue.top()
    queue.pop()

    pixel = entry.second
    area = local_contributive_area(pixel, flow, mask)

    while not queue.empty():

        entry = queue.top()
        queue.pop()

        other_pixel = entry.second
        other_area = local_contributive_area(other_pixel, flow, mask)

        if other_area > area:

            pixel = other_pixel
            area = other_area

        else:

            break

    for i in range(mini, maxi+1):
        for j in range(minj, maxj+1):
            
            if ingrid(height, width, i, j):
                mask[i, j] = False

    return Outlet(pixel, area)

def polygon_outlets(float[:, :] geometry, short[:, :] flow, unsigned char[:, :] mask, tuple gdal_transform):
    """
    """

    cdef:

        long height = flow.shape[0], width = flow.shape[1]
        long i, j, mini, minj, maxi, maxj
        int x
        short direction
        GeoTransform transform
        GridExtent extent
        Cell pixel
        # Outlet outlet
        vector[Outlet] outlets

    transform = transform_from_gdal(gdal_transform)
    extent = grid_extent(geometry, transform)

    mini = extent.first.first
    minj = extent.first.second
    maxi = extent.second.first
    maxj = extent.second.second

    for i in range(mini, maxi+1):
        for j in range(minj, maxj+1):

            if ingrid(height, width, i, j) and mask[i, j]:

                direction = flow[i, j]
                x = ilog2(direction)
                ix = i + ci[x]
                jx = j + cj[x]

                if ingrid(height, width, ix, jx) and not mask[ix, jx]:

                    pixel = Cell(i, j)
                    lca = local_contributive_area(pixel, flow, mask)
                    # outlet = Outlet(pixel, lca)
                    # outlets.append(outlet)
                    outlets.push_back(Outlet(pixel, lca))

    return outlets

@cython.boundscheck(False)
@cython.wraparound(False)
def subgrid_outlets(dict geometries, short[:, :] flow, ContributingArea[:, :] acc, tuple gdal_transform, feedback=None):
    """
    Find outlets for every geometry (polygon) in `geometries`
    """

    cdef:

        long height = flow.shape[0], width = flow.shape[1]
        unsigned char[:, :] mask
        dict outlets
        GeoTransform transform
        Cell pixel
        ContributingArea area
        Outlet outlet

    outlets = dict()
    mask = np.zeros((height, width), dtype=np.uint8)
    transform = transform_from_gdal(gdal_transform)
    
    total = 100.0 / len(geometries) if len(geometries) else 0

    for current, (fid, geometry) in enumerate(geometries.items()):

        if feedback.isCanceled():
            break

        outlet = subgrid_outlet(geometry, flow, acc, mask, transform)
        pixel = outlet.first
        area = outlet.second

        if pixel.first != -1:
            outlets[fid] = outlet

        feedback.setProgress(int(current*total))

    return outlets

@cython.boundscheck(False)
@cython.wraparound(False)
def tile_outlets(short[:, :] flow, unsigned char[:, :] mask):

    cdef:

        long height = flow.shape[0], width = flow.shape[1]
        long i, j, ix, jx
        vector[Outlet] outlets
        vector[Cell] targets
        Cell pixel
        Outlet outlet
        int x
        ContributingArea area

    for i in range(height):
        for j in range(width):

            if mask[i, j]:

                direction = flow[i, j]
                
                if direction == -1 or direction == 0:
                    continue

                x = ilog2(direction)
                ix = i + ci[x]
                jx = j + cj[x]

                if not ingrid(height, width, ix, jx) or not mask[ix, jx]:

                    pixel = Cell(i, j)
                    area = local_contributive_area(pixel, flow, mask)
                    outlets.push_back(Outlet(pixel, area))
                    targets.push_back(Cell(ix, jx))

    return outlets, targets

@cython.boundscheck(False)
@cython.wraparound(False)
def outlet(short[:, :] flow, long i0, long j0):

    cdef:

        long height = flow.shape[0], width = flow.shape[1]
        long i = i0, j = j0, ix = -1, jx = -1
        int x

    while ingrid(height, width, i, j):

        direction = flow[i, j]

        if direction == -1:
            break

        ix, jx = i, j

        if direction == 0:
            break

        x = ilog2(direction)
        i = i + ci[x]
        j = j + cj[x]

    return ix, jx
