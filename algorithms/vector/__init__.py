from .LineMidpoints import LineMidpoints
from .PointsAlongPolygon import PointsAlongPolygon
from .PointsInPolygon import PointsInPolygon
from .RandomPoissonDiscSampling import RandomPoissonDiscSampling
from .RegularHexPoints import RegularHexPoints
from .RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from .SciPyVoronoiPolygons import SciPyVoronoiPolygons

def vector_algorithms():

    return [
        LineMidpoints(),
        PointsAlongPolygon(),
        PointsInPolygon(),
        RandomPoissonDiscSampling(),
        RegularHexPoints(),
        RemoveSmallPolygonalObjects(),
        SciPyVoronoiPolygons()
    ]
