# -*- coding: utf-8 -*-

"""
Disaggregate spatial values

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
def disaggregate(
    float[:, :] geometry,
    unsigned char[:, :] zone,
    float value,
    float increment,
    object rio_transform,
    unsigned char[:, :] mask,
    float[:, :] out):
    """
    Disaggregate uniformly `value`
    over the extent given by `geometry`(must be a polygon)
    onto target pixels in raster `zone`.

    Parameters
    ----------

    geometry: array-like, size (n, 2), dtype=float32
        A sequence of n coordinate pairs,
        defining a polygon exterior ring,
        first and last point must be the same

    zone: array-like, dtype=uint8
        A raster which defines where the targets pixels are :
        values in `zone`should be such as
        target pixels = 2, fallback pixels = 1, nodata = 0

    value: int
        The value to disaggregat over the extent of `geometry`

    rio_transform: RasterIO Affine object
        Geo-transform from geometry coordinate system
        to raster pixel coordinates.

    mask: array-like, dtype=uint8, same size as `zone`
        A temporary raster that can be reused between successive
        calls  to `disaggregate` ;
        `mask` must be initialized to zeros.

    out: array-like, dtype=float32, same size as `zone`
        Target raster, receiving disaggregated increments
        that sum up to `value`
    """

    cdef:

        GridExtent extent
        long height = zone.shape[0], width = zone.shape[1]
        long i, j, mini, minj, maxi, maxj
        GeoTransform transform
        int[:] randomi, randomj
        int k, area = 0, urban_area = 0

        float total = 0.0

    transform = transform_from_rasterio(rio_transform)

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

            if zone[i, j] > 0 and point_in_ring(p, geometry):

                if zone[i, j] == 1:
                    area += 1
                
                if zone[i, j] == 2:
                    area += 1
                    urban_area += 1
                
                mask[i, j] = True

    if area + urban_area == 0:
        return

    while total < value:

        randomi = np.random.randint(low=mini, high=maxi+1, size=10000, dtype=np.int32)
        randomj = np.random.randint(low=minj, high=maxj+1, size=10000, dtype=np.int32)

        for k in range(10000):

            i = randomi[k]
            j = randomj[k]

            if ingrid(height, width, i, j) and mask[i, j]:

                if (urban_area > 0 and zone[i, j] == 2) or \
                    (urban_area == 0 and zone[i, j] == 1):
                    
                    out[i, j] += increment
                    total += increment
                    
                    if total >= value:
                        break

    for i in range(mini, maxi+1):
        for j in range(minj, maxj+1):
            
            if ingrid(height, width, i, j):
                mask[i, j] = False