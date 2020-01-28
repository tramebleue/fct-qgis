cdef struct GeoTransform:

    float origin_x
    float origin_y
    float scale_x
    float scale_y
    float shear_x
    float shear_y

cdef GeoTransform transform_from_gdal(gdal_transform):
    """
    Convert GDAL GeoTransform Tuple to internal GeoTransform
    """

    cdef GeoTransform transform

    transform.origin_x = gdal_transform[0]
    transform.origin_y = gdal_transform[3]
    transform.scale_x = gdal_transform[1]
    transform.scale_y = gdal_transform[5]
    transform.shear_x = gdal_transform[2]
    transform.shear_y = gdal_transform[4]

    return transform

cdef GeoTransform transform_from_rasterio(rio_transform):
    """
    Convert RasterIO Affine Transform Object to internal GeoTransform
    """

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

def pixeltoxy(int row, int col, transform, gdal=True):
    """
    Transform raster pixel coordinates (py, px)
    into real world coordinates (x, y)

    Parameters
    ----------

    row, col: int
        raster pixel coordinates

    transform: object
        GDAL GeoTransform or RasterIO Affine Transform Object

    gdal: boolean
        True if `transform` is a GDAL GeoTransform,
        False if it is a Rasterio Affine Transform

    Returns
    -------

    (x, y): float
        x and y real world coordinates
        
    """

    if gdal:
        gt = transform_from_gdal(transform)
    else:
        gt = transform_from_rasterio(transform)

    return pixeltopoint(Cell(row, col), gt)

def xytopixel(float x, float y, transform, gdal=True):
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (py, px)

    Parameters
    ----------

    x, y: float
        x and y real world coordinates

    transform: object
        GDAL GeoTransform or RasterIO Affine Transform Object

    gdal: boolean
        True if `transform` is a GDAL GeoTransform,
        False if it is a Rasterio Affine Transform

    Returns
    -------

    (row, col): int
        raster pixel coordinates
    """

    if gdal:
        gt = transform_from_gdal(transform)
    else:
        gt = transform_from_rasterio(transform)

    return pointtopixel(Point(x, y), gt)


@cython.boundscheck(False)
@cython.wraparound(False)
@cython.cdivision(True)
def worldtopixel(np.float32_t[:, :] coordinates, transform, gdal=True):
    """
    Transform real world coordinates (x, y)
    into raster pixel coordinates (py, px)

    Parameters
    ----------

    coordinates: array, shape (n, 2), dtype=float32
        array of (x, y) coordinates

    transform: object
        GDAL GeoTransform or RasterIO Affine Transform Object

    gdal: boolean
        True if `transform` is a GDAL GeoTransform,
        False if it is a Rasterio Affine Transform 

    Returns
    -------

    Raster pixel coordinates
    as an array of shape (n, 2), dtype=int32
    """

    cdef:

        long length = coordinates.shape[0], k
        np.int32_t[:, :] pixels
        GeoTransform gt
        # Point point
        # Cell pixel
        float x, y
        float det, a, b, c, d, e, f

    if gdal:
        gt = transform_from_gdal(transform)
    else:
        gt = transform_from_rasterio(transform)

    pixels = np.zeros((length, 2), dtype=np.int32)

    with nogil:

        if gt.shear_x == 0 and gt.shear_y == 0:

            for k in range(length):

                # point =  Point(coordinates[k, 0], coordinates[k, 1])
                x = coordinates[k, 0]
                y = coordinates[k, 1]
                
                # pixel = pointtopixel(point, gt)
                pixels[k, 0] = lround((y - gt.origin_y) / gt.scale_y - 0.5)
                pixels[k, 1] = lround((x - gt.origin_x) / gt.scale_x - 0.5)

        else:

            # Compute inverse transform only once

            det = gt.scale_x*gt.scale_y - gt.shear_x*gt.shear_y
            a = -gt.shear_y / det
            b = gt.scale_x / det
            c = (gt.origin_x*gt.shear_y - gt.scale_x*gt.origin_y) / det
            d = gt.scale_y / det
            e = -gt.shear_x / det
            f = (gt.shear_x*gt.origin_y - gt.origin_x*gt.scale_y) / det

            for k in range(length):

                # point =  Point(coordinates[k, 0], coordinates[k, 1])
                x = coordinates[k, 0]
                y = coordinates[k, 1]
                
                pixels[k, 0] = lround((a*x + b*y + c) - 0.5)
                pixels[k, 1] = lround((d*x + e*y + f) - 0.5)
                
    return np.asarray(pixels)

@cython.boundscheck(False)
@cython.wraparound(False)
def pixeltoworld(np.int32_t[:, :] pixels, transform, gdal=True):
    """
    Transform raster pixel coordinates (py, px)
    into real world coordinates (x, y)

    Parameters
    ----------

    pixels: array, shape (n, 2), dtype=int32
        array of (row, col) raster coordinates

    transform: object
        GDAL GeoTransform or RasterIO Affine Transform Object

    gdal: boolean
        True if `transform` is a GDAL GeoTransform,
        False if it is a Rasterio Affine Transform 

    Returns
    -------

    Real world coordinates
    as an array of shape (n, 2), dtype=float32
    """

    cdef:

        long length = pixels.shape[0], k
        np.float32_t[:, :] coordinates
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

    return np.asarray(coordinates)
