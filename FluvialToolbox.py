from PyQt4.QtGui import QIcon
from processing.core.Processing import Processing
from processing.core.AlgorithmProvider import AlgorithmProvider
from common import *
from main import *
from graph import *
from modeler import *
from spatial_components import *

class FluvialToolbox(object):

    def __init__(self, iface):
        self.provider = FluvialToolboxProvider()

    def initGui(self):
        Processing.addProvider(self.provider)

    def unload(self):
        Processing.removeProvider(self.provider)


class FluvialToolboxProvider(AlgorithmProvider):
	
    def __init__(self):
        super(FluvialToolboxProvider, self).__init__()

    def unload(self):
        super(FluvialToolboxProvider, self).unload()

    def getName(self):
        return 'Fluvial Toolbox'

    def getDescription(self):
        return 'Fluvial Toolbox'

    # def getIcon(self):
    #    return QIcon(":/plugins/fluvialtoolbox/icon.svg")

    def _loadAlgorithms(self):
        algs = [ SplitLine(),
                 SplitLineIntoSegments(),
                 JoinByNearest(),
                 Sequencing(),
                 DifferentialRasterThreshold(),
                 RemoveSmallPolygonalObjects(),
                 ExtremePoints(),
                 ExtractUniquePoints(),
                 NearTable(),
                 SplitLineAtNearestPoint(),
                 ValleyBottom(),
                 CenterLine(),
                 ValleyBottomWidth(),
                 SimpleRasterStatistics(),
                 Sequencing2(),
                 SelectStreamFromSourceToOutlet(),
                 SelectStreamFromOutletToSources(),
                 SelectGraphCycle(),
                 SelectionReverseFlowDirection(),
                 GraphEndpoints(),
                 SelectByDistance(),
                 MeasureDistanceToPointLayer(),
                 AggregateLineSegments(),
                 AggregateLineSegmentsByCat(),
                 TrianglesToEdges(),
                 PointOnSurface(),
                 FastDeleteExteriorPolygons(),
                 UniqueValuesTable(),
                 ComputeFrictionCost(),
                 RandomPoints(),
                 ShortestDistanceToTargets(),
                 NodesFromEdges(),
                 LineMidpoints(),
                 MeasurePointsAlongLine(),
                 ProjectPointsAlongLine(),
                 SegmentMeanSlope(),
                 DirectedGraphFromUndirected(),
                 LongestPathInDirectedAcyclicGraph(),
                 PolygonSkeleton(),
                 DisaggregatePolygon(),
                 LongestPathInDirectedAcyclicGraphMultiFlow(),
                 MedialAxis(),
                 LocalFeatureSize(),
                 PlanformMetrics(),
                 PathLengthOrder(),
                 SelectNearestFeature(),
                 ExtractRasterValueAtPoints(),
                 StrahlerOrder(),
                 SimplifyVisvalingam(),
                 LeftRightDGO(),
                 BinaryClosing() ]
        try:
          from shapelish import *
          algs.append(FastVariableDistanceBuffer())
          algs.append(FastFixedDistanceBuffer())
        except ImportError:
          pass
        self.algs.extend(algs)