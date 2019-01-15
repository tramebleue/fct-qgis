from .BinaryClosing import BinaryClosing
from .DifferentialRasterThreshold import DifferentialRasterThreshold
from .FocalMean import FocalMean
from .RasterDifference import RasterDifference
from .RasterInfo import RasterInfo

def rasterAlgorithms():

    return [
        BinaryClosing(),
        DifferentialRasterThreshold(),
        FocalMean(),
        # ExtractRasterValueAtPoints(),
        # SimpleRasterStatistics()
        RasterDifference(),
        RasterInfo()
    ]
