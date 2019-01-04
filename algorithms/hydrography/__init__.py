from .AggregateLineSegments import AggregateLineSegments
from .NetworkNodes import NetworkNodes

def hydrography_algorithms():

    return [
        AggregateLineSegments(),
        NetworkNodes()
    ]