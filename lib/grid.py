import numpy as np

def reverse_direction(x):
    """ Return D8 inverse search directions
    """

    return (x + 4) % 8

# D8 directions, clockwise starting from North
#       0   1   2   3   4   5   6   7
#       N  NE   E  SE   S  SW   W  NW
#
#       NW=7 | N=0 | NE=1
#     --------------------
#        W=6 |  x  |  E=2
#     --------------------
#       SW=5 | S=4 | SE=3

D8_DIR = np.array([0, 1, 2, 3, 4, 5, 6, 7])
D8POW2 = np.power(2, D8_DIR, dtype=np.uint8)

# Flow direction value of upward cells
# in each search direction,
# e.g. cell north (search index 0) of cell x is connected to cell x
#      if its flow direction is 4 (southward)

D8_UPWARD = reverse_direction(D8_DIR)
D8POW2_UPWARD = np.power(2, D8_UPWARD, dtype=np.uint8)

# D8 directions in 3x3 neighborhood

D8POW2_MAT = np.power(2, np.array([7, 0, 1, 6, 0, 2, 5, 4, 3], dtype=np.uint8))
D8POW2_MAT[5] = 0

# D8 search directions

D8_SEARCH = np.array([
    [-1, -1,  0,  1,  1,  1,  0, -1],
    [ 0,  1,  1,  1,  0, -1, -1, -1]
]).T

def ingrid(data, i, j):
    """ Tests if cell (i, j) is within the range of data

    Parameters
    ----------

    data: array-like, ndim=2
        Input raster

    i: int
        Row index

    j: int
        Column index

    Returns
    -------

    True if coordinates (i, j) fall within data, False otherwise.
    """

    height, width = data.shape
    return (i >= 0) and (i < height) and (j >= 0) and (j < width)