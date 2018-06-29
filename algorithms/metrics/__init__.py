from LocalFeatureSize import LocalFeatureSize
from PlanformMetrics import PlanformMetrics
from SegmentMeanSlope import SegmentMeanSlope
from Sinuosity import Sinuosity
from Sum import Sum
from WeightedMean import WeightedMean

def metricsAlgorithms():

    return [
        LocalFeatureSize(),
        PlanformMetrics(),
        SegmentMeanSlope(),
        Sinuosity(),
        Sum(),
        WeightedMean()
    ]