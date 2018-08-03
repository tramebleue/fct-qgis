from DeduplicateLines import DeduplicateLines
from JoinByNearest import JoinByNearest
from LineMidpoints import LineMidpoints
from MeasureDistanceToPointLayer import MeasureDistanceToPointLayer
from MergeGeometries import MergeGeometries
from PointOnSurface import PointOnSurface
from RandomPoints import RandomPoints
from RegularHexPoints import RegularHexPoints
from RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from SafePolygonIntersection import SafePolygonIntersection
from SelectByDistance import SelectByDistance
from SelectNearestFeature import SelectNearestFeature
from SplitLine import SplitLine
from SplitLineIntoSegments import SplitLineIntoSegments
from UniquePoints import UniquePoints
from UniqueValuesTable import UniqueValuesTable
from UpdateFieldByExpression import UpdateFieldByExpression
from UpdateFieldByExpressionInPlace import UpdateFieldByExpressionInPlace


def vectorAlgorithms():

    return [
        DeduplicateLines(),
        JoinByNearest(),
        LineMidpoints(),
        MeasureDistanceToPointLayer(),
        MergeGeometries(),
        PointOnSurface(),
        RandomPoints(),
        RegularHexPoints(),
        RemoveSmallPolygonalObjects(),
        SafePolygonIntersection(),
        SelectByDistance(),
        SelectNearestFeature(),
        SplitLine(),
        SplitLineIntoSegments(),
        UniquePoints(),
        UniqueValuesTable(),
        UpdateFieldByExpression(),
        UpdateFieldByExpressionInPlace()
    ]