from heapq import heappop, heappush, heapify
from functools import total_ordering

def triangle_area(a, b, c):

    return abs((a.x - c.x) * (b.y - a.y) - (a.x - b.x) * (c.y - a.y)) / 2

class Point(object):

    def __init__(self, x, y, z=0):
        self.x = x
        self.y = y
        # do not store z, we don't need it
        # self.z = z

class Triangle(object):

    def __init__(self, a, b, c):
        self.a = Point(*a)
        self.b = Point(*b)
        self.c = Point(*c)
        # Store original b for later output
        self.bo = b
        self.weight = self.area
        self.entry = None

    @property
    def area(self):
        return triangle_area(self.a, self.b, self.c)

@total_ordering
class QueueEntry(object):

    def __init__(self, index, triangle):
        self.index = index
        self.triangle = triangle
        self.removed = False
        triangle.entry = self

    def __lt__(self, other):
        return self.triangle.weight < other.triangle.weight

    def __eq__(self, other):
        return self.triangle.weight == other.triangle.weight


def pre_simplify(linestring):
    """
    Visvalingam's non-destructive line simplification

    [1] Visvalingam, M. and J. D. Whyatt. (1992)
        Line Generalisation By Repeated Elimination of Smallest Area.
        Cartographic Information Systems Research Group, University of Hull.

    [2] https://bost.ocks.org/mike/simplify/

    [3] https://github.com/topojson/topojson-simplify/blob/9c893b2/src/presimplify.js
        BSD-3 Licensed
    """

    if len(linestring) > 2:

        triangles = [ Triangle(a, b, c)
                      for a, b, c
                      in zip(linestring[:-2], linestring[1:-1], linestring[2:]) ]

        heap = heapify([ QueueEntry(i, t) for i, t in enumerate(triangles) ])
        max_weight = 0

        while heap:

            entry = heappop(heap)
            if entry.removed:
                continue

            i = entry.index
            triangle = entry.triangle
            w = triangle.weight

            if w < max_weight:
                triangle.weight = max_weight
            else:
                max_weight = w

            if i > 0:

                t = triangles[i-1]
                t.c = triangle.c
                t.weight = t.area
                t.entry.removed = True
                heappush(heap, QueueEntry(i-1, t))
                

            if i < len(triangles)-1:
                
                t = triangles[i+1]
                t.a = triangle.a
                t.weight = t.area
                t.entry.removed = True
                heappush(heap, QueueEntry(i+1, t))

        start = (linestring[0], float('inf'))
        end = (linestring[-1], float('inf'))
        return [ start ] + [ (t.bo, t.weight) for t in triangles ] + [ end ]

    else:

        return zip(linestring, [ float('inf') ] * len(linestring))

def simplify(linestring, min_weight):

    return [ p for p, weight in filter(lambda x: x[1] >= min_weight, pre_simplify(linestring)) ]
