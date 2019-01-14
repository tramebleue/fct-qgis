import numpy as np
from heapq import heapify, heappop, heappush

# D8 directions in 3x3 neighborhood

d8_directions = np.power(2, np.array([7, 0, 1, 6, 0, 2, 5, 4, 3], dtype=np.uint8))
d8_directions[5] = 0

# D8 search directions, clockwise starting from North
#       0   1   2   3   4   5   6   7
#       N  NE   E  SE   S  SW   W  NW
#
#       NW=7 | N=0 | NE=1
#     --------------------
#        W=6 |  x  |  E=2
#     --------------------
#       SW=5 | S=4 | SE=3

ci = [-1, -1,  0,  1,  1,  1,  0, -1]
cj = [ 0,  1,  1,  1,  0, -1, -1, -1]

# Flow direction value of upward cells
# in each search direction,
# e.g. cell north (search index 0) of cell x is connected to cell x
#      if its flow direction is 2^4 (southward)

upward = np.power(2, np.array([4,  5,  6,  7,  0,  1,  2, 3], dtype=np.uint8))

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

def reverse_direction(x):
    """ Return D8 inverse search directions
    """

    return (x + 4) % 8

def flow_accumulation(flow, out=None, feedback=None):
    """ Fill sinks of digital elevation model (DEM),
        based on the algorithm of Wang & Liu (2006).

    Parameters
    ----------

    flow: array-like
        D8 Flow direction raster (ndim=2)

    out: array-like
        Same shape and dtype as elevations, initialized to nodata

    Returns
    -------

    Flow accumulation raster
    """

    height, width = flow.shape
    nodata = -1

    if out is None:
        out = np.full(flow.shape, -1, dtype=np.int8)

    inflow = np.full(flow.shape, -1, dtype=np.int8)

    # progress = TermProgressBar(2*width*height)
    # progress.write('Input is %d x %d' % (width, height))
    feedback.setProgressText('Find source cells ...')

    # We use a heap queue to sort cells
    # from lower z to higher z.
    # Remember python's heapq is a min-heap.
    stack = list()
    total = 100.0 / (height*width)
    ncells = 0

    for i in range(height):

        if feedback.isCanceled():
            break

        for j in range(width):

            direction = flow[i, j]

            if direction != nodata:

                out[i, j] = 1
                inflowij = 0

                for x in range(8):

                    ix = i + ci[x]
                    jx = j + cj[x]

                    if ingrid(flow, ix, jx) and (flow[ix, jx] == upward[x]):
                        inflowij += 1

                if inflowij == 0:
                    stack.append((i, j))

                inflow[i, j] = inflowij
                ncells += 1

        feedback.setProgress(int((i*width)*total))

    feedback.setProgressText('Accumulate ...')

    feedback.pushInfo('%s inputs data cells' % ncells)
    total = 100.0 / ncells
    current = 0

    while stack:

        if feedback.isCanceled():
            break

        i, j = stack.pop()
        inflow[i, j] = -1

        direction = flow[i, j]
        if direction == 0:
            current += 1
            continue

        x = int(np.log2(direction))
        ix = i + ci[x]
        jx = j + cj[x]

        while ingrid(flow, ix, jx) and inflow[ix, jx] > 0:

            out[ix, jx] = out[ix, jx] + out[i, j]
            inflow[ix, jx] = inflow[ix, jx] - 1

            # check if we reached a confluence cell

            if inflow[ix, jx] > 0:
                break

            # otherwise accumulate downward

            direction = flow[ix, jx]
            if direction == 0:
                current += 1
                break

            inflow[ix, jx] = -1
            i, j = ix, jx
            x = int(np.log2(direction))
            ix = i + ci[x]
            jx = j + cj[x]

            current += 1

        current += 1
        feedback.setProgress(int(current*total))

    return out

def test():

    class Feedback(object):

        #pylint:disable=missing-docstring,no-self-use

        def setProgressText(self, msg):
            print(msg)

        def setProgress(self, progress):
            pass

        def isCanceled(self):
            return False

        def pushInfo(self, msg):
            print(msg)

    flow = np.power(2, np.array(
        [[4, 3, 4, 4],
         [3, 2, 3, 4],
         [2, 2, 2, 3]]))

    return flow_accumulation(flow, feedback=Feedback())
