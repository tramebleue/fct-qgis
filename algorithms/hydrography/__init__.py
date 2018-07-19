from AggregateLineSegments import AggregateLineSegments
from AggregateLineSegmentsByCat import AggregateLineSegmentsByCat
from DensifyNetworkNodes import DensifyNetworkNodes
# from ExtremePoints import ExtremePoints
from IdentifyNetworkNodes import IdentifyNetworkNodes
from LocatePolygonAlongLine import LocatePolygonAlongLine
# from LocatePolygonAlongLinearNetwork import LocatePolygonAlongLinearNetwork
from LengthOrder import LengthOrder
from LongestPathInDirectedAcyclicGraph import LongestPathInDirectedAcyclicGraph
from LongestPathInDirectedAcyclicGraphMultiFlow import LongestPathInDirectedAcyclicGraphMultiFlow
# from MarkMainDrain import MarkMainDrain
from MatchNearestLine import MatchNearestLine
from MatchNearestLineUpdate import MatchNearestLineUpdate
from MatchNetworkNodes import MatchNetworkNodes
# from MatchNetworkNodesTopology import MatchNetworkNodesTopology
from MatchNetworkSegments import MatchNetworkSegments
from MeasureLinesFromOutlet import MeasureLinesFromOutlet
from MeasurePointsAlongLine import MeasurePointsAlongLine
from NetworkNodes import NetworkNodes
from ProjectPointsAlongLine import ProjectPointsAlongLine
from ReverseFlowDirection import ReverseFlowDirection
from SelectConnectedComponents import SelectConnectedComponents
from SelectDownstreamComponents import SelectDownstreamComponents
from SelectFullLengthPaths import SelectFullLengthPaths
from SelectGraphCycle import SelectGraphCycle
from SelectMainDrain import SelectMainDrain
from SelectShortTributaries import SelectShortTributaries
from SelectUpstreamComponents import SelectUpstreamComponents
from Sequencing import Sequencing
from StrahlerOrder import StrahlerOrder


def hydrographyAlgorithms():

    return [

        AggregateLineSegments(),
        AggregateLineSegmentsByCat(),
        DensifyNetworkNodes(),
        # ExtremePoints(),
        IdentifyNetworkNodes(),
        LengthOrder(),
        LocatePolygonAlongLine(),
        # LocatePolygonAlongLinearNetwork(),
        LongestPathInDirectedAcyclicGraph(),
        LongestPathInDirectedAcyclicGraphMultiFlow(),
        # MarkMainDrain(),
        MatchNearestLine(),
        MatchNearestLineUpdate(),
        MatchNetworkNodes(),
        # MatchNetworkNodesTopology(),
        MatchNetworkSegments(),
        MeasureLinesFromOutlet(),
        MeasurePointsAlongLine(),
        NetworkNodes(),
        ProjectPointsAlongLine(),
        ReverseFlowDirection(),
        SelectConnectedComponents(),
        SelectDownstreamComponents(),
        SelectFullLengthPaths(),
        SelectGraphCycle(),
        SelectMainDrain(),
        SelectShortTributaries(),
        SelectUpstreamComponents(),
        Sequencing(),
        StrahlerOrder()

    ]