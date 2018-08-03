# coding: utf-8

import numpy as np
from visvalingam import simplify
from collections import defaultdict
from functools import partial
import json

class Arc(object):

    def __init__(self, index_a, index_b):

        self.a = index_a
        self.b = index_b
        self.next = None
        self.count = 0

def copy_key(instance, receiver, *keys):

    for key in keys:
        if instance.has_key(key) and instance[key]:

            receiver[key] = json.loads(json.dumps(instance[key]))

def extract(geojson):
    """
    [1] GeoJSON Specification
        https://tools.ietf.org/html/rfc7946
    """

    coordinates = list()
    lines = list()
    rings = list()

    def extract_line(line_coords):

        a = len(coordinates)
        coordinates.extend(map(tuple, line_coords))
        b = len(coordinates) - 1

        arc = Arc(a, b)
        lines.append(arc)

        return arc

    def extract_ring(line_coords):

        a = len(coordinates)
        coordinates.extend(map(tuple, line_coords))
        b = len(coordinates) - 1

        arc = Arc(a, b)
        rings.append(arc)

        return arc

    def extract_geometry(component):

        # TODO encode bbox, id fields

        component_type = component['type']

        if component_type == 'Point':
            return {
                'coordinates': list(component['coordinates']),
                'type': component_type
            }

        elif component_type == 'LineString':
            return {
                'arcs': extract_line(component['coordinates']),
                'type': component_type
            }

        elif component_type == 'Polygon':
            return {
                'arcs': map(extract_ring, component['coordinates']),
                'type': component_type
            }

        elif component_type == 'MultiPoint':
            return {
                'coordinates': list(component['coordinates']),
                'type': component_type
            }

        elif component_type == 'MultiLineString':
            return {
                'arcs': map(extract_line, component['coordinates']),
                'type': component_type
            }

        elif component_type == 'MultiPolygon':
            return {
                'arcs': [ map(extract_ring, polygon) for polygon in component['coordinates'] ],
                'type': component_type
            }

        elif component_type == 'GeometryCollection':
            return {
                'geometries': map(extract_geometry, component['geometries']),
                'type': component_type
            }

        elif component_type == 'Feature':
            geometry = extract_geometry(component['geometry'])
            copy_key(component, geometry, 'id', 'properties')
            return geometry

        elif component_type == 'FeatureCollection':
            return {
                'geometries': map(extract_geometry, component['features']),
                'type': component_type
            }

        else:

            raise ValueError('Unexpected type %s' % component_type)

    def extract_object(obj):
        o = extract_geometry(obj)
        copy_key(obj, o, 'bbox', 'crs')
        return o

    if geojson.has_key('type'):

        objects = extract_object(geojson)
    else:
        objects = { key: extract_object(obj) for key, obj in geojson.items() }

    return np.array(coordinates), lines, rings, objects



def index(coordinates):

    coordinates_map = dict()
    indexes = np.full(len(coordinates), -1, dtype=np.int32)

    for i in xrange(len(coordinates)):

        c = tuple(coordinates[i])
        if coordinates_map.has_key(c):
            indexes[i] = coordinates_map[c]
        else:
            indexes[i] = i
            coordinates_map[c] = i

    del coordinates_map

    return indexes

def junction(coordinates, lines, rings):

    n = len(coordinates)

    indexes = index(coordinates)
    visited = np.full(n, -1, dtype=np.int32)
    left = np.full(n, -1, dtype=np.int32)
    right = np.full(n, -1, dtype=np.int32)
    junctions = np.zeros(n, dtype=np.int16)
    junction_count = 0

    def sequence(i, previous_index, current_index, next_index):

        if visited[current_index] == i:
            return 0

        visited[current_index] = i
        left_index = left[current_index]
        count = 0

        if left_index >= 0:

            right_index = right[current_index]

            if (left_index != previous_index or right_index != next_index) and \
               (left_index != next_index or right_index != previous_index):

               junctions[current_index] = 1
               count += 1

        else:

            left[current_index] = previous_index
            right[current_index] = next_index

        return count

    for i, line in enumerate(lines):

        start = line.a
        end = line.b
        current_index = indexes[start]
        next_index = indexes[start + 1]

        start += 1
        junctions[current_index] = 1
        junction_count += 1

        while start < end:

            start += 1
            previous_index = current_index
            current_index = next_index
            next_index = indexes[start]
            junction_count += sequence(i, previous_index, current_index, next_index)

        junctions[next_index] = 1
        junction_count += 1

    visited = np.full(n, -1, dtype=np.int32)

    for i, ring in enumerate(rings):

        start = ring.a
        end = ring.b

        previous_index = indexes[end - 1]
        current_index = indexes[start]
        next_index = indexes[start + 1]

        start += 1
        junction_count += sequence(i, previous_index, current_index, next_index)

        while start < end:

            start += 1
            previous_index = current_index
            current_index = next_index
            next_index = indexes[start]
            junction_count += sequence(i, previous_index, current_index, next_index)

    # del visited
    # del left
    # del right

    junction_set = { tuple(coordinates[indexes[i]])
                     for i in range(n)
                     if junctions[indexes[i]] == 1 }

    # junction_set = set()
    # for i in range(n):

    #     j = indexes[i]
    #     if junctions[j] == 1:
    #         junction_set.add(coordinates[j])

    # del indexes
    # del junctions

    return junction_set

def rotate(x, start, mid, end):

    # ABCDE -> EDCBA -> CDEAB
    # x[ start:end+1 ] = np.flip(x[ start:end+1 ], 0)
    # x[ start:mid ] = np.flip(x[ start:mid ], 0)
    # x[ mid:end+1 ] = np.flip(x[ mid:end+1 ], 0)

    x[ start:end+1 ] = np.roll(x[ start:end+1 ], end-mid+1, 0)

def cut(coordinates, lines, rings):

    junctions = junction(coordinates, lines, rings)

    for line in lines:

        start = mid = line.a
        end = line.b

        while mid < end-1:
            mid += 1
            if tuple(coordinates[mid]) in junctions:
                line.b = mid
                line.next = Arc(mid, end)
                line = line.next

    for ring in rings:

        start = mid = ring.a
        end = ring.b
        ring_fixed = (tuple(coordinates[start]) in junctions)

        while mid < end-1:
            mid += 1
            if tuple(coordinates[mid]) in junctions:
                if ring_fixed:
                    ring.b = mid
                    ring.next = Arc(mid, end)
                    ring = ring.next
                else:
                    rotate(coordinates, start, mid, end-1)
                    coordinates[end] = coordinates[start]
                    ring_fixed = True
                    mid = start

def count_lines(lines):

    count = 0

    for i in range(len(lines)):

        line = lines[i]
        while line.next:
            line = line.next
            count += 1
        count += 1

    return count

def dedup(coordinates, lines, rings):

    arc_index = defaultdict(list)
    arcs = list()

    def minimum_offset(arc):

        mid = arc.a
        minimum = mid
        minimum_point = coordinates[mid]

        while mid < arc.b-1:
            mid += 1
            point = coordinates[mid]
            if point[0] < minimum_point[0] or point[0] == minimum_point[0] and point[1] < minimum_point[1]:
                minimum = mid
                minimum_point = point

        return minimum - arc.a

    def equal_line(x, y):

        n = x.b - x.a
        if n != (y.b - y.a):
            return False

        return np.all([ coordinates[ x.a + i ] == coordinates[ y.a + i ] for i in range(n+1) ])

    def equal_line_reverse(x, y):

        n = x.b - x.a
        if n != (y.b - y.a):
            return False

        return np.all([ coordinates[ x.a + i ] == coordinates[ y.b - i ]
                     for i in range(n+1) ])

    def equal_ring(x, y):

        n = x.b - x.a
        if n != (y.b - y.a):
            return False

        offset_x = minimum_offset(x)
        offset_y = minimum_offset(y)

        return np.all([ coordinates[ x.a + ((i + offset_x) % n) ] == coordinates[ y.a + ((i + offset_y) % n) ]
                     for i in range(n+1) ])

    def equal_ring_reverse(x, y):

        n = x.b - x.a
        if n != (y.b - y.a):
            return False

        offset_x = minimum_offset(x)
        offset_y = n - minimum_offset(y)

        return np.all([ coordinates[ x.a + ((i + offset_x) % n) ] == coordinates[ y.b - ((i + offset_y) % n) ]
                     for i in range(n+1) ])

    def dedup_line(arc):

        for other_arc in arc_index[tuple(coordinates[arc.a])]:
            if equal_line(arc, other_arc):
                arc.a = other_arc.a
                arc.b = other_arc.b
                return

        for other_arc in arc_index[tuple(coordinates[arc.b])]:
            if equal_line_reverse(arc, other_arc):
                arc.a = other_arc.b
                arc.b = other_arc.a
                return

        arc_index[tuple(coordinates[arc.a])].append(arc)
        arc_index[tuple(coordinates[arc.b])].append(arc)
        
        arcs.append(arc)

    def dedup_ring(arc):

        for other_arc in arc_index[tuple(coordinates[arc.a])]:
            if equal_line(arc, other_arc):
                arc.a = other_arc.a
                arc.b = other_arc.b
                return
            if equal_line_reverse(arc, other_arc):
                arc.a = other_arc.b
                arc.b = other_arc.a
                return

        offset = minimum_offset(arc)

        for other_arc in arc_index[tuple(coordinates[arc.a + offset])]:
            if equal_ring(arc, other_arc):
                arc.a = other_arc.a
                arc.b = other_arc.b
                return
            if equal_ring_reverse(arc, other_arc):
                arc.a = other_arc.b
                arc.b = other_arc.a
                return
            
        arc_index[tuple(coordinates[arc.a + offset])].append(arc)

        arcs.append(arc)

    for line in lines:
        while line:
            dedup_line(line)
            line = line.next

    for ring in rings:
        if ring.next:
            while ring:
                dedup_line(ring)
                ring = ring.next
        else:
            dedup_ring(ring)

    return arcs

def arc_geometry(coordinates, arc):

    a = arc.a
    b = arc.b

    if a > b:
        return np.flip(coordinates[b:a+1], 0).tolist()
    else:
        return coordinates[a:b+1].tolist()

def delta_encode(coordinates):

    x0, y0 = coordinates[0]
    delta_coords = [[ x0, y0 ]]

    for x, y in coordinates[1:]:

        if not (x == x0 and y == y0):
            delta_coords.append([ x - x0, y - y0 ])
            x0 = x
            y0 = y
    
    if len(delta_coords) == 1:
        delta_coords.append([ 0, 0 ])

    return delta_coords

def delta_decode(delta_coords):

    x, y = delta_coords[0]
    coordinates = [[ x, y ]]

    for dx, dy in delta_coords[1:]:
        x = x + dx
        y = y + dy
        coordinates.append([ x, y ])

    return coordinates


def component_geometry(coordinates, component):

    coords = list()
    arc = component
    
    while arc:

        geom = arc_geometry(coordinates, arc.a, arc.b)
        last_point = geom[-1]
        coords.extend(geom[:-1])
        arc = arc.next

    coords.append(last_point)

    return coords

def delta(coordinates, arcs):

    return map(delta_encode, map(partial(arc_geometry, coordinates), arcs))

def map_geometries(arc_index, objects):

    def map_arc(arc):

        arcs = list()
        current = arc

        while current:

            start = current.a
            end   = current.b

            if start > end:
                index = -arc_index[(end, start)]
            else:
                index = arc_index[(start, end)]

            arcs.append(index)
            current = current.next

        return arcs

    def component_arcs(component):

        component_type = component['type']

        if component_type == 'Point':
            pass

        elif component_type == 'LineString':
            component['arcs'] = map_arc(component['arcs'])

        elif component_type == 'Polygon':
            component['arcs'] = map(map_arc, component['arcs'])

        elif component_type == 'MultiPoint':
            pass

        elif component_type == 'MultiLineString':
            component['arcs'] = map(map_arc, component['arcs'])

        elif component_type == 'MultiPolygon':
            component['arcs'] = [ map(map_arc, polygon) for polygon in component['arcs'] ]

        elif component_type == 'GeometryCollection' or component_type == 'FeatureCollection':
            for geometry in component['geometries']:
                component_arcs(geometry)

        elif component_type == 'Feature':
            component_arcs(component['geometry'])

        return component

    if objects.has_key('type'):
        
        component_arcs(objects)

    else:

        return { key: component_arcs(obj) for key, obj in objects.items() }

    return objects


def topology(geojson, quantization=1e6, simplification=0):
    """
    Convert GeoJSON to TopoJSON.

    Parameters
    ----------

    geojson: dict-like
        plain GeoJSON object
        or dictionary of named GeoJSON objects

    quantization: number, > 1
        size of the grid used to round-off coordinates.
        If <= 1, no quantization is used.

    Returns
    -------

    topojson: dict-like TopoJSON object

    Notes
    -----

    [1] Bostock, Mike (2013) How To Infer Topology
        https://bost.ocks.org/mike/topology/

    [2] Bostock's Nodejs reference implementation
        https://github.com/topojson/topojson-server/tree/6c1709b/src
        BSD-3 Licensed
    """

    coordinates, lines, rings, objects = extract(geojson)

    minx = np.min(coordinates[:, 0])
    miny = np.min(coordinates[:, 1])
    maxx = np.max(coordinates[:, 0])
    maxy = np.max(coordinates[:, 1])

    if quantization > 1:
        kx = (minx == maxx) and 1 or (maxx - minx)
        ky = (miny == maxy) and 1 or (maxy - miny)
        quantized = np.int32(np.round((coordinates - (minx, miny)) / (kx, ky) * quantization))
    else:
        kx = ky = 1
        quantized = coordinates

    cut(quantized, lines, rings)
    arcs = dedup(quantized, lines, rings)
    arc_index = { (arc.a, arc.b): i+1 for i, arc in enumerate(arcs) }

    if simplification > 0:

        arcs = map(delta_encode, simplify(map(partial(arc_geometry, quantized), arcs), simplification))

    else:

        arcs = delta(quantized, arcs)

    topo = {
        'arcs': arcs,
        'objects': map_geometries(arc_index, objects),
        'bbox': [ minx, miny, maxx, maxy ],
        'type': 'Topology'
    }

    if quantization > 1:

        topo['transform'] = {
            'scale': [ kx / quantization, ky / quantization ],
            'translate': [ minx, miny ]
        }

    return topo

def unpack(topojson):
    """
    Convert TopoJSON object to GeoJSON. 
    """

    if not (topojson.has_key('type') and topojson['type'] == 'Topology'):
        raise KeyError('Not a valid TopoJSON object')

    geojson = dict()

    arcs = [ delta_decode(arc) for arc in topojson['arcs'] ]

    if topojson.has_key('transform'):
        sx, sy = topojson['transform']['scale']
        tx, ty = topojson['transform']['translate']
        arcs = [ (np.array(arc) * (sx, sy)) + (tx, ty) for arc in arcs ]
    else:
        arcs = [ np.array(arc) for arc in arcs ]

    def unpack_linestring(geometry):

        coordinates = list()

        for index in geometry:

            if index < 0:
                arc = np.flip(arcs[-index-1], 0).tolist()
            else:
                arc = arcs[index-1].tolist()

            last_point = arc[-1]
            coordinates.extend(arc[:-1])

        coordinates.append(last_point)

        return coordinates

    def unpack_ring(geometry):

        ring = unpack_linestring(geometry)
        if tuple(ring[0]) != tuple(ring[-1]): print ring
        assert(tuple(ring[0]) == tuple(ring[-1]))
        return ring

    def unpack_geometry(component):

        component_type = component['type']

        if component.has_key('properties'):
            feature = {
                'geometry': unpack_geometry({ 'arcs': component['arcs'], 'type': component_type }),
                'type': 'Feature'
            }
            copy_key(component, feature, 'id', 'bbox', 'properties')
            return feature

        elif component_type == 'Point':
            return {
                'coordinates': component['coordinates'],
                'type': component_type
            }

        elif component_type == 'LineString':
            return {
                'coordinates': unpack_linestring(component['arcs']),
                'type': component_type
            }
            

        elif component_type == 'Polygon':
            return {
                'coordinates': map(unpack_ring, component['arcs']),
                'type': component_type
            }

        elif component_type == 'MultiPoint':
            return {
                'coordinates': component['coordinates'],
                'type': component_type
            }

        elif component_type == 'MultiLineString':
            return {
                'coordinates': map(unpack_linestring, component['arcs']),
                'type': component_type
            }

        elif component_type == 'MultiPolygon':
            return {
                'coordinates': [ map(unpack_ring, polygon) for polygon in component['arcs'] ],
                'type': component_type
            }

        elif component_type == 'GeometryCollection':
            return {
                'geometries': [ unpack_geometry(geometry) for geometry in component['geometries'] ],
                'type': component_type
            }

        elif component_type == 'FeatureCollection':
            return {
                'features': [ unpack_geometry(geometry) for geometry in component['geometries'] ],
                'type': component_type
            }
            
        else:

            raise ValueError('Unexpected type %s' % component_type)

    def unpack_object(obj):

        o = unpack_geometry(obj)
        copy_key(obj, o, 'id', 'bbox', 'crs')
        return o

    if topojson['objects'].has_key('type'):

        geojson = unpack_object(topojson['objects'])

    else:

        geojson = { key: unpack_object(obj)
                    for key, obj in topojson['objects'].items() }

    return geojson

def test_geom():
    import shapely.geometry
    return shapely.geometry.MultiPolygon([
            [[ (0,0), (1,0), (1,1), (0,1) ], []],
            [[ (1,0), (2,0), (2,1), (1,1) ], []]
        ])


