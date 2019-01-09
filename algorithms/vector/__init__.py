from .PointsInPolygon import PointsInPolygon
from .RandomPoissonDiscSampling import RandomPoissonDiscSampling
from .RegularHexPoints import RegularHexPoints
from .RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from .SciPyVoronoiPolygons import SciPyVoronoiPolygons

def vector_algorithms():

    return [
        PointsInPolygon(),
        RandomPoissonDiscSampling(),
        RegularHexPoints(),
        RemoveSmallPolygonalObjects(),
        SciPyVoronoiPolygons()
    ]
