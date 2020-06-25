def distance_to_segment(a, b, c):
    """
    Distance from C to segment [AB].
    a, b, c: array-like of pairs of (x, y) coordinates
    """

    segment_ab = b - a
    segment_ac = c - a
    length_ab = np.linalg.norm(segment_ab, axis=1)
    # length_ac = np.linalg.norm(segment_ac, axis=1)

    # dot = AB.AC / AB^2
    #     = |AC| * cos(AB, AC) / |AB|
    dot = np.sum(segment_ab*segment_ac, axis=1) / (length_ab**2)
    dot[dot < 0.0] = 0.0
    dot[dot > 1.0] = 1.0

    nearest = np.array([
        a[:, 0] + dot*segment_ab[:, 0],
        a[:, 1] + dot*segment_ab[:, 1]]).T

    distance = np.linalg.norm(nearest - c, axis=1)
    distance[np.isnan(distance)] = np.infty

    return distance

def cross_distance(a, b, c):
    """
    Signed distance from point C to (infinite) line (AB)
    """

    segment_ab = b - a
    segment_ac = c - a
    length_ab = np.linalg.norm(segment_ab, axis=1)

    return np.cross(segment_ab, segment_ac) / length_ab

def signed_distance(
        points, nearest_indices, reference_points,
        transform=transform,
        signed=True):
    """
    Calculate the distance of `points`
    to the nearest segment defined by `reference_points`,
    knowing the nearest point index in `reference_points`.
    """

    # A-----B-----C
    #     ^
    #     P (nearest point B)

    # a = pixeltoworld(np.take(reference_points, nearest_indices-1, axis=0, mode='wrap'), transform)
    # b = pixeltoworld(np.take(reference_points, nearest_indices, axis=0, mode='wrap'), transform)
    # c = pixeltoworld(np.take(reference_points, nearest_indices+1, axis=0, mode='wrap'), transform)

    a = np.take(reference_points, nearest_indices-1, axis=0, mode='wrap')
    b = np.take(reference_points, nearest_indices, axis=0, mode='wrap')
    c = np.take(reference_points, nearest_indices+1, axis=0, mode='wrap')

    # cross_distance_before = cross_distance(a, b, points)
    # cross_distance_after = cross_distance(b, c, points)
    # nearest_is_after = np.abs(cross_distance_before) > np.abs(cross_distance_after)

    # distance = np.copy(cross_distance_before)
    # distance[nearest_is_after] = cross_distance_after[nearest_is_after]

    # if signed:
    #     return distance

    # return np.abs(distance)

    distance_before = distance_to_segment(a, b, points)
    distance_after = distance_to_segment(b, c, points)

    nearest_is_after = distance_before > distance_after
    a[nearest_is_after] = b[nearest_is_after]
    b[nearest_is_after] = c[nearest_is_after]
    distance = np.copy(distance_before)
    distance[nearest_is_after] = distance_after[nearest_is_after]

    del c
    # del distance_before
    # del distance_after
    del nearest_is_after

    if signed:

        dx = b[:, 0] - a[:, 0]
        dy = b[:, 1] - a[:, 1]
        nx = points[:, 0] - a[:, 0]
        ny = points[:, 1] - a[:, 1]
        cross = (dx * ny) - (dy * nx)

        # TODO
        # handle zeros in cross where distance > 0

        return np.sign(cross) * distance * transform[1]

        # return cross_distance(a, b, points) * transform[1]

    return distance * transform[1]