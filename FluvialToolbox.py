from PyQt4.QtGui import *
from processing.core.Processing import Processing
from processing.core.AlgorithmProvider import AlgorithmProvider
from SplitLineString import SplitLineString
from ValleyBottomMask import ValleyBottomMask
from ValleyBottom import ValleyBottom
from CleanValleyBottom import CleanValleyBottom

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
        self.alglist = [ SplitLineString(),
                         ValleyBottomMask(),
                         CleanValleyBottom(),
                         ValleyBottom() ]
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