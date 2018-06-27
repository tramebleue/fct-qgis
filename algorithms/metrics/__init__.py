from LocalFeatureSize import LocalFeatureSize
from PlanformMetrics import PlanformMetrics
from SegmentMeanSlope import SegmentMeanSlope

def metricsAlgorithms():

    return [
        LocalFeatureSize(),
        PlanformMetrics(),
        SegmentMeanSlope()
    ]