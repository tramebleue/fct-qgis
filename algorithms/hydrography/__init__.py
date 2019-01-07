from .AggregateLineSegments import AggregateLineSegments
from .LengthOrder import LengthOrder
from .NetworkNodes import NetworkNodes
from .StrahlerOrder import StrahlerOrder

def hydrography_algorithms():

    return [
        AggregateLineSegments(),
        LengthOrder(),
        NetworkNodes(),
        StrahlerOrder()
    ]