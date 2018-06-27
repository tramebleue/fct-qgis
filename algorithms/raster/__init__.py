from BinaryClosing import BinaryClosing
from DifferentialRasterThreshold import DifferentialRasterThreshold
from ExtractRasterValueAtPoints import ExtractRasterValueAtPoints
from SimpleRasterStatistics import SimpleRasterStatistics

def rasterAlgorithms():

    return [
        BinaryClosing(),
        DifferentialRasterThreshold(),
        ExtractRasterValueAtPoints(),
        SimpleRasterStatistics()
    ]