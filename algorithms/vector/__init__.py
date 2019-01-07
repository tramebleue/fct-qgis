from .PointsInPolygon import PointsInPolygon
from .RandomPoissonDiscSampling import RandomPoissonDiscSampling
from .RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects

def vector_algorithms():

    return [
        PointsInPolygon(),
        RandomPoissonDiscSampling(),
        RemoveSmallPolygonalObjects()
    ]