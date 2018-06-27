from JoinByNearest import JoinByNearest
from LineMidpoints import LineMidpoints
from MeasureDistanceToPointLayer import MeasureDistanceToPointLayer
from PointOnSurface import PointOnSurface
from RandomPoints import RandomPoints
from RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from SafePolygonIntersection import SafePolygonIntersection
from SelectByDistance import SelectByDistance
from SelectNearestFeature import SelectNearestFeature
from SplitLine import SplitLine
from SplitLineIntoSegments import SplitLineIntoSegments
from UniquePoints import UniquePoints
from UniqueValuesTable import UniqueValuesTable


def vectorAlgorithms():

    return [
        JoinByNearest(),
        LineMidpoints(),
        MeasureDistanceToPointLayer(),
        PointOnSurface(),
        RandomPoints(),
        RemoveSmallPolygonalObjects(),
        SafePolygonIntersection(),
        SelectByDistance(),
        SelectNearestFeature(),
        SplitLine(),
        SplitLineIntoSegments(),
        UniquePoints(),
        UniqueValuesTable()
    ]