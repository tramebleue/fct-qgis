import array
from cpython cimport array
from libc.math cimport sqrt, atan, atan2, pi, cos, sin, tan, acos
from libcpp.map cimport map

cdef extern from "<algorithm>" namespace "std":
    T max[T](T a, T b) nogil
    void swap[T](T a, T b) nogil

#                                    0   1   2   3   4   5   6   7
#                                    N  NE   E  SE   S  SW   W  NW
cdef int[8] ci = array.array('i', [ -1, -1,  0,  1,  1,  1,  0, -1 ])
cdef int[8] cj = array.array('i', [  0,  1,  1,  1,  0, -1, -1, -1 ])


# upward = np.power(2, np.array([ 4,  5,  6,  7,  0,  1,  2,  3 ], dtype=np.uint8))
cdef unsigned char[8] upward = array.array('B', [ 16,  32,  64,  128,  1,  2,  4,  8 ])


cdef inline bint ingrid(long height, long width, long i, long j) nogil:

    return (i >= 0) and (i < height) and (j >= 0) and (j < width)

cdef inline bint ingrid3x3(long height, long width, long i, long j) nogil:

    return (i >= 1) and (i < height-1) and (j >= 1) and (j < width-1)

cdef inline int ilog2(unsigned char x) nogil:

    cdef int r = 0

    if x == 0:
        return -1

    while x != 1:
        r += 1
        x = x >> 1

    return r

cdef inline int pow2(unsigned char x) nogil:

    return 1 << x


cdef double[:, :] distance_2d(double rx, double ry):

    cdef double[:, :] r

    r = np.zeros((3, 3))
    r[ 1, 0 ] = r[ 1, 2 ] = rx
    r[ 0, 1 ] = r[ 2, 1 ] = ry
    r[ 0, 0 ] = r[ 2, 2 ] = r[ 0, 2 ] = r[ 2, 0 ] = sqrt(rx*rx + ry*ry)

    return r

cdef double deg2rad(double x) nogil:

    return x * pi / 180