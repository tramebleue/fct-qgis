from PyQt4.QtGui import QIcon
from processing.core.Processing import Processing
from processing.core.AlgorithmProvider import AlgorithmProvider
from common import *
from main import *

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

    def unload(self):
        super(FluvialToolboxProvider, self).unload()

    def getName(self):
        return 'Fluvial Toolbox'

    def getDescription(self):
        return 'Fluvial Toolbox'

    # def getIcon(self):
    #    return QIcon(":/plugins/fluvialtoolbox/icon.svg")

    def _loadAlgorithms(self):
        self.algs.extend([ SplitLine(),
                           SplitLineIntoSegments(),
                           JoinByNearest(),
                           Sequencing(),
                           DifferentialRasterThreshold(),
                           RemoveSmallPolygonalObjects(),
                           ExtremePoints(),
                           NearTable(),
                           SplitLineAtNearestPoint(),
                           ValleyBottom(),
                           CenterLine(),
                           ValleyBottomWidth() ])