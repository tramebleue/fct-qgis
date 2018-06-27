from AggregateLineSegments import AggregateLineSegments
from AggregateLineSegmentsByCat import AggregateLineSegmentsByCat
from DensifyNetworkNodes import DensifyNetworkNodes
from ExtremePoints import ExtremePoints
from IdentifyNetworkNodes import IdentifyNetworkNodes
from LongestPathInDirectedAcyclicGraph import LongestPathInDirectedAcyclicGraph
from LongestPathInDirectedAcyclicGraphMultiFlow import LongestPathInDirectedAcyclicGraphMultiFlow
from MarkMainDrain import MarkMainDrain
from MatchNetworkSegments import MatchNetworkSegments
from MeasureDGO import MeasureDGO
from MeasureLinesFromOutlet import MeasureLinesFromOutlet
from MeasurePointsAlongLine import MeasurePointsAlongLine
from NetworkNodes import NetworkNodes
from PairNetworkNodes import PairNetworkNodes
from PathLengthOrder import PathLengthOrder
from ProjectPointsAlongLine import ProjectPointsAlongLine
from SelectConnectedComponents import SelectConnectedComponents
from SelectFullLengthPaths import SelectFullLengthPaths
from SelectGraphCycle import SelectGraphCycle
from SelectionReverseFlowDirection import SelectionReverseFlowDirection
from SelectStreamFromOutletToSources import SelectStreamFromOutletToSources
from SelectStreamFromSourceToOutlet import SelectStreamFromSourceToOutlet
from Sequencing import Sequencing
from StrahlerOrder import StrahlerOrder


def hydrographyAlgorithms():

    return [
        AggregateLineSegments(),
        AggregateLineSegmentsByCat(),
        DensifyNetworkNodes(),
        ExtremePoints(),
        IdentifyNetworkNodes(),
        LongestPathInDirectedAcyclicGraph(),
        LongestPathInDirectedAcyclicGraphMultiFlow(),
        MarkMainDrain(),
        MatchNetworkSegments(),
        MeasureDGO(),
        MeasureLinesFromOutlet(),
        MeasurePointsAlongLine(),
        NetworkNodes(),
        PairNetworkNodes(),
        PathLengthOrder(),
        ProjectPointsAlongLine(),
        SelectConnectedComponents(),
        SelectFullLengthPaths(),
        SelectGraphCycle(),
        SelectionReverseFlowDirection(),
        SelectStreamFromOutletToSources(),
        SelectStreamFromSourceToOutlet(),
        Sequencing(),
        StrahlerOrder()
    ]