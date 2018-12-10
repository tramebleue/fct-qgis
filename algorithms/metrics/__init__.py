from DetrendDEM import DetrendDEM
from FilterByMinRank import FilterByMinRank
from LocalFeatureSize import LocalFeatureSize
from OrthogonalTransects import OrthogonalTransects
from PlanformMetrics import PlanformMetrics
from SegmentMeanSlope import SegmentMeanSlope
from SegmentMeanValue import SegmentMeanValue
from SegmentPlanarSlope import SegmentPlanarSlope
from Sinuosity import Sinuosity
from Sum import Sum
from WeightedMean import WeightedMean

def metricsAlgorithms():

    return [
        DetrendDEM(),
    	FilterByMinRank(),
        LocalFeatureSize(),
        OrthogonalTransects(),
        PlanformMetrics(),
        SegmentMeanSlope(),
        SegmentMeanValue(),
        SegmentPlanarSlope(),
        Sinuosity(),
        Sum(),
        WeightedMean()
    ]