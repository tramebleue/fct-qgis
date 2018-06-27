from DisaggregatePolygon import DisaggregatePolygon
from LeftRightDGO import LeftRightDGO
from MedialAxis import MedialAxis
from PolygonSkeleton import PolygonSkeleton
from ValleyBottom import ValleyBottom

def spatial_componentsAlgorithms():

    return [
        DisaggregatePolygon(),
        LeftRightDGO(),
        MedialAxis(),
        PolygonSkeleton(),
        ValleyBottom()
    ]
