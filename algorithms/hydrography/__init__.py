from .AggregateLineSegments import AggregateLineSegments
from .NetworkNodes import NetworkNodes
from .StrahlerOrder import StrahlerOrder

def hydrography_algorithms():

    return [
        AggregateLineSegments(),
        NetworkNodes(),
        StrahlerOrder()
    ]