from PyQt4.QtGui import *
from processing.core.Processing import Processing
from processing.core.AlgorithmProvider import AlgorithmProvider
from SplitLine import SplitLine
from DifferentialRasterThreshold import DifferentialRasterThreshold
from ValleyBottom import ValleyBottom
from RemoveSmallPolygonalObjects import RemoveSmallPolygonalObjects
from ExtremePoints import ExtremePoints
from NearTable import NearTable
from SplitLineAtNearestPoint import SplitLineAtNearestPoint
from CenterLine import CenterLine

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
        self.alglist = [ SplitLine(),
                         DifferentialRasterThreshold(),
                         RemoveSmallPolygonalObjects(),
                         ExtremePoints(),
                         NearTable(),
                         SplitLineAtNearestPoint(),
                         ValleyBottom(),
                         CenterLine() ]
        for alg in self.alglist:
            alg.provider = self

    def unload(self):
        super(FluvialToolboxProvider, self).unload()

    def getName(self):
        return 'Fluvial Toolbox'

    def getDescription(self):
        return 'Fluvial Toolbox'

    # def getIcon(self):
    #    return QIcon(":/plugins/concavehull/icon.svg")

    def _loadAlgorithms(self):
        self.algs = self.alglist