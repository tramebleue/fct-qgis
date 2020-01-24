cdef struct GeoTransform:

    float origin_x
    float origin_y
    float scale_x
    float scale_y
    float shear_x
    float shear_y

cdef GeoTransform transform_from_gdal(gdal_transform):

    cdef GeoTransform transform

    transform.origin_x = gdal_transform[0]
    transform.origin_y = gdal_transform[3]
    transform.scale_x = gdal_transform[1]
    transform.scale_y = gdal_transform[5]
    transform.shear_x = gdal_transform[2]
    transform.shear_y = gdal_transform[4]

    return transform

cdef GeoTransform transform_from_rasterio(rio_transform):

    cdef GeoTransform transform

    transform.origin_x = rio_transform.c
    transform.origin_y = rio_transform.f
    transform.scale_x = rio_transform.a
    transform.scale_y = rio_transform.e
    transform.shear_x = rio_transform.d
    transform.shear_y = rio_transform.b

    return transform

cdef Point pixeltopoint(Cell pixel, GeoTransform transform) nogil:
    """
    Transform raster pixel coordinates (py, px)
    into real world coordinates (x, y)
    """

    cdef float x, y

    if transform.shear_x == 0 and transform.shear_y == 0:

        x = (pixel.second + 0.5) * transform.scale_x + transform.origin_x
        y = (pixel.first + 0.5) * transform.scale_y + transform.origin_y

    else:

        # complete affine transform formula
        x = (pixel.second + 0.5) * transform.scale_x + (pixel.first + 0.5) * transform.shear_y + transform.origin_x
        y = (pixel.first + 0.5) * transform.scale_y + (pixel.second + 0.5) * transform.shear_x + transform.origin_y

    return Point(x, y)

@cython.cdivision(True) 
cdef Cell pointtopixel(Point p, GeoTransform transform) nogil:
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (py, px)
    """

    cdef long i, j
    cdef float det

    if transform.shear_x == 0 and transform.shear_y == 0:

        j = lround((p.first - transform.origin_x) / transform.scale_x - 0.5)
        i = lround((p.second - transform.origin_y) / transform.scale_y - 0.5)

    else:

        # complete affine transform formula
        det = transform.scale_x*transform.scale_y - transform.shear_x*transform.shear_y
        j = lround((p.first*transform.scale_y - p.second*transform.shear_x + \
            transform.shear_x*transform.origin_y - transform.origin_x*transform.scale_y) / det - 0.5)
        i = lround((-p.first*transform.shear_y + p.second*transform.scale_x + \
             transform.origin_x*transform.shear_y - transform.scale_x*transform.origin_y) / det - 0.5)
    
    return Cell(i, j)

@cython.boundscheck(False)
@cython.wraparound(False)
def worldtopixel(float[:, :] coordinates, transform, gdal=True):
    """
    DOCME
    """

    cdef:

        long length = coordinates.shape[0], k
        unsigned int[:, :] pixels
        GeoTransform gt
        Point point
        Cell pixel

    if gdal:
        gt = transform_from_gdal(transform)
    else:
        gt = transform_from_rasterio(transform)

    pixels = np.zeros((length, 2), dtype=np.uint32)

    with nogil:

        for k in range(length):

            point =  Point(coordinates[k, 0], coordinates[k, 1])
            pixel = pointtopixel(point, gt)
            pixels[k, 0] = pixel.first
            pixels[k, 1] = pixel.second

    return pixels

@cython.boundscheck(False)
@cython.wraparound(False)
def pixeltoworld(unsigned int[:, :] pixels, transform, gdal=True):
    """
    DOCME
    """

    cdef:

        long length = pixels.shape[0], k
        float[:, :] coordinates
        GeoTransform gt
        Point point
        Cell pixel

    if gdal:
        gt = transform_from_gdal(transform)
    else:
        gt = transform_from_rasterio(transform)

    coordinates = np.zeros((length, 2), dtype=np.float32)

    with nogil:

        for k in range(length):

            pixel = Cell(pixels[k, 0], pixels[k, 1])
            point = pixeltopoint(pixel, gt)
            coordinates[k, 0] = point.first
            coordinates[k, 1] = point.second

    return coordinates


