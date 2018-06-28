from LocalFeatureSize import LocalFeatureSize
from PlanformMetrics import PlanformMetrics
from SegmentMeanSlope import SegmentMeanSlope
from Sinuosity import Sinuosity

def metricsAlgorithms():

    return [
        LocalFeatureSize(),
        PlanformMetrics(),
        SegmentMeanSlope(),
        Sinuosity()
    ]