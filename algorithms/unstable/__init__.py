from CenterLine import CenterLine
from LeftRightBox import LeftRightBox
from MatchPolygonWithMostImportantLine import MatchPolygonWithMostImportantLine
from MatchPolygonWithNearestCentroid import MatchPolygonWithNearestCentroid
# from NearTable import NearTable
# from ProjectPointsAlongMostImportantLine import ProjectPointsAlongMostImportantLine
from SimplifyVisvalingam import SimplifyVisvalingam
from SplitLineAtNearestPoint import SplitLineAtNearestPoint

def unstableAlgorithms():

    return [
        CenterLine(),
        LeftRightBox(),
        MatchPolygonWithMostImportantLine(),
        MatchPolygonWithNearestCentroid(),
        # NearTable(),
        # ProjectPointsAlongMostImportantLine(),
        SimplifyVisvalingam(),
        SplitLineAtNearestPoint()
    ]