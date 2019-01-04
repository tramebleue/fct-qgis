from .AggregateLineSegments import AggregateLineSegments
from .AggregateLineSegmentsByCat import AggregateLineSegmentsByCat
from .NetworkNodes import NetworkNodes

def hydrography_algorithms():

    return [
        AggregateLineSegments(),
        AggregateLineSegmentsByCat(),
        NetworkNodes()
    ]