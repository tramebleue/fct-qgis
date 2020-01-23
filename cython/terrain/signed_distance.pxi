@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
def extract_pixels_within_distance(float[:, :] distance, float max_distance):
    """
    Extract pixels in `distance` having value lesser or equal to `max_distance`
    """

    cdef:

        long height = distance.shape[0], width = distance.shape[1]
        long i, j
        vector[Cell] pixels

    with nogil:

        for i in range(height):
            for j in range(width):

                if distance[i, j] > 0 and distance[i, j] <= max_distance:
                    pixels.push_back(Cell(i, j))

    return np.int32(pixels)

@cython.boundscheck(False)
@cython.wraparound(False)
@cython.nonecheck(False)
@cython.cdivision(True) 
def signed_distance(float[:, :] a, float[:, :] b, float[:, :] c):
    """
    Distance from C to segment [AB].
    a, b, c: array-like of pairs of (x, y) coordinates
    """

    # segment_ab = b - a
    # segment_ac = c - a
    # length_ab = np.linalg.norm(segment_ab, axis=1)
    # # length_ac = np.linalg.norm(segment_ac, axis=1)

    # # dot = AB.AC / AB^2
    # #     = |AC| * cos(AB, AC) / |AB|
    # dot = np.sum(segment_ab*segment_ac, axis=1) / (length_ab**2)
    # dot[dot < 0.0] = 0.0
    # dot[dot > 1.0] = 1.0

    # nearest = np.array([
    #     a[:, 0] + dot*segment_ab[:, 0],
    #     a[:, 1] + dot*segment_ab[:, 1]]).T

    # distance = np.linalg.norm(nearest - c, axis=1)
    # distance[np.isnan(distance)] = np.infty

    # signed_dist = np.cross(segment_ab, segment_ac) / length_ab

    # return distance, signed_dist, dot

    cdef:

        long length = a.shape[0], k
        float ax, ay, bx, by, cx, cy
        float abx, aby, acx, acy, sqab
        float dot, nx, ny

        float[:] dist, signed_dist, pos

    assert (b.shape[0] == length) and (c.shape[0] == length), "Operands must have same length"
    assert (a.shape[1] > 1) and (b.shape[1] > 1) and (c.shape[1] > 1), "Coordinate dimension must be >= 2"

    dist = np.zeros(length, dtype=np.float32)
    signed_dist = np.zeros(length, dtype=np.float32)
    pos = np.zeros(length, dtype=np.float32)

    with nogil:

        for k in range(length):

            ax = a[k, 0]
            ay = a[k, 1]
            bx = b[k, 0]
            by = b[k, 1]
            cx = c[k, 0]
            cy = c[k, 1]

            abx = bx - ax
            aby = by - ay
            acx = cx - ax
            acy = cy - ay
            sqab = abx**2 + aby**2

            # Parametric location of C projection on segment [AB]

            if sqab > 0.0:
                dot = (abx*acx + aby*acy) / sqab
                if dot < 0.0:
                    dot = 0.0
                if dot > 1.0:
                    dot = 1.0
            else:
                dot = 0.0

            # C projection (nx, ny) on segment [AB]

            nx = ax + dot*abx
            ny = ay + dot*aby

            # Distance from C to segment [AB]

            dist[k] = sqrt((cx - nx)**2 + (cy - ny)**2)

            # Signed distance from C to infinite line (AB)

            if sqab > 0.0:
                signed_dist[k] = ((abx * acy) - (aby * acx)) / sqrt(sqab)
            else:
                signed_dist[k] = dist[k]

            pos[k] = dot

    return dist, signed_dist, pos

# def side_of_nearest_segment(pixels, points, segments, out, feedback):
#     """
#     """

#     cdef:

#         long length = pixels.shape[0], n = segments.shape[0]
#         long current, row, col, k
#         float x, y, total

#     total = 100.0 / length if length else 0.0

#     for current in range(length):

#         row = pixels[current, 0]
#         col = pixels[current, 1]
#         x = points[current, 0]
#         y = points[current, 1]

#         # TODO use index or quadtree

#         point = np.array([(x, y)])
#         dist, signed_dist, pos = signed_distance(segments[:, :2], segments[:, 2:], point)

#         min_dist = np.infty
#         min_signed = np.infty
#         nearest = 0

#         for k in range(n):

#             if dist[k] < min_dist:

#                 min_dist = dist[k]
#                 min_signed = signed_dist[k]
#                 nearest = k

#             elif dist[k] == min_dist and abs(signed_dist[k]) < abs(min_signed):

#                 min_signed = signed_dist[k]
#                 nearest = k

#         out[row, col] = np.sign(min_signed)

#         feedback.setProgress(int(current*total))

