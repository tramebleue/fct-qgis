from PyQt5.QtCore import QCoreApplication

from qgis.core import (QgsApplication,
                       QgsProcessingProvider)

from .algorithms.hydrography import hydrography_algorithms
from .algorithms.metrics import metrics_algorithms
from .algorithms.raster import rasterAlgorithms
from .algorithms.spatial_components import spatial_componentsAlgorithms
from .algorithms.vector import vector_algorithms

class FluvialCorridorToolboxPlugin:

    def __init__(self, iface):

        # self.iface = iface
        self.provider = FluvialCorridorToolboxProvider()

    def initGui(self):

        QgsApplication.processingRegistry().addProvider(self.provider)

    def unload(self):

        QgsApplication.processingRegistry().removeProvider(self.provider)

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FluvialCorridorToolbox', message)


class FluvialCorridorToolboxProvider(QgsProcessingProvider):

    def id(self):
        return 'fct'

    def name(self):
        return 'Fluvial Corridor Toolbox'
    
    def longName(self):
        return 'Fluvial Corridor Toolbox'

    def loadAlgorithms(self):

        algs = hydrography_algorithms() + \
               metrics_algorithms() + \
               spatial_componentsAlgorithms() + \
               rasterAlgorithms() + \
               vector_algorithms()

        for alg in algs:
            self.addAlgorithm(alg)
