from Detrend import Detrend
from FilterByMinRank import FilterByMinRank
from LocalFeatureSize import LocalFeatureSize
from PlanformMetrics import PlanformMetrics
from SegmentMeanSlope import SegmentMeanSlope
from SegmentMeanValue import SegmentMeanValue
from Sinuosity import Sinuosity
from Sum import Sum
from WeightedMean import WeightedMean

def metricsAlgorithms():

    return [
    	Detrend(),
    	FilterByMinRank(),
        LocalFeatureSize(),
        PlanformMetrics(),
        SegmentMeanSlope(),
        SegmentMeanValue(),
        Sinuosity(),
        Sum(),
        WeightedMean()
    ]