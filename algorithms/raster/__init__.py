from .BinaryClosing import BinaryClosing
from .DifferentialRasterThreshold import DifferentialRasterThreshold

def rasterAlgorithms():

    return [
        BinaryClosing(),
        DifferentialRasterThreshold()
        # ExtractRasterValueAtPoints(),
        # SimpleRasterStatistics()
    ]