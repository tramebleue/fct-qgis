from .BinaryClosing import BinaryClosing
from .DifferentialRasterThreshold import DifferentialRasterThreshold
from .FocalMean import FocalMean
from .RasterDifference import RasterDifference
from .RasterResolution import RasterResolution

def rasterAlgorithms():

    return [
        BinaryClosing(),
        DifferentialRasterThreshold(),
        FocalMean(),
        # ExtractRasterValueAtPoints(),
        # SimpleRasterStatistics()
        RasterDifference(),
        RasterResolution()
    ]
