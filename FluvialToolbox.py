from PyQt4.QtCore import QSettings, QTranslator, QCoreApplication
from PyQt4.QtGui import QIcon, QAction
from processing.core.Processing import Processing
from processing.core.AlgorithmProvider import AlgorithmProvider
from common import *
from main import *
from graph import *
from modeler import *
from spatial_components import *
from maptools import ReverseFlowDirectionTool

class FluvialToolbox(object):

    def __init__(self, iface):
        self.iface = iface
        self.actions = list()
        self.provider = FluvialToolboxProvider()
        self.menu = self.tr(u'&Fluvial Toolbox')
        self.toolbar = self.iface.addToolBar(u'FluvialToolbox')
        self.toolbar.setObjectName(u'FluvialToolbox')

    def initGui(self):

        icon_path = ':/plugins/fluvialtoolbox/icon.png'
        
        Processing.addProvider(self.provider)

        self.reverseFlowDirectionTool = ReverseFlowDirectionTool(self.iface.mapCanvas(), None)
        action = self.add_action(
                icon_path,
                self.tr('Reverse Flow Direction'),
                callback=self.activateReverseFlowDirectionTool,
                parent=self.iface.mainWindow())
        action.setCheckable(True)
        self.reverseFlowDirectionTool.setAction(action)


    def unload(self):

        Processing.removeProvider(self.provider)

        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Fluvial Toolbox'),
                action)
            self.iface.removeToolBarIcon(action)
        
        # Unset the map tool in case it's set
        self.iface.mapCanvas().unsetMapTool(self.reverseFlowDirectionTool)

    def activateReverseFlowDirectionTool(self):
        self.iface.mapCanvas().setMapTool(self.reverseFlowDirectionTool)

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the InaSAFE toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FluvialToolbox', message)


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
        algs = [ SplitLine(),
                 SplitLineIntoSegments(),
                 JoinByNearest(),
                 Sequencing(),
                 DifferentialRasterThreshold(),
                 RemoveSmallPolygonalObjects(),
                 ExtremePoints(),
                 ExtractUniquePoints(),
                 NearTable(),
                 SplitLineAtNearestPoint(),
                 ValleyBottom(),
                 CenterLine(),
                 ValleyBottomWidth(),
                 SimpleRasterStatistics(),
                 Sequencing2(),
                 SelectStreamFromSourceToOutlet(),
                 SelectStreamFromOutletToSources(),
                 SelectGraphCycle(),
                 SelectionReverseFlowDirection(),
                 GraphEndpoints(),
                 SelectByDistance(),
                 MeasureDistanceToPointLayer(),
                 AggregateLineSegments(),
                 AggregateLineSegmentsByCat(),
                 TrianglesToEdges(),
                 PointOnSurface(),
                 FastDeleteExteriorPolygons(),
                 UniqueValuesTable(),
                 ComputeFrictionCost(),
                 RandomPoints(),
                 ShortestDistanceToTargets(),
                 NodesFromEdges(),
                 LineMidpoints(),
                 MeasurePointsAlongLine(),
                 ProjectPointsAlongLine(),
                 SegmentMeanSlope(),
                 DirectedGraphFromUndirected(),
                 LongestPathInDirectedAcyclicGraph(),
                 PolygonSkeleton(),
                 DisaggregatePolygon(),
                 LongestPathInDirectedAcyclicGraphMultiFlow(),
                 MedialAxis(),
                 LocalFeatureSize(),
                 PlanformMetrics(),
                 PathLengthOrder(),
                 SelectNearestFeature(),
                 ExtractRasterValueAtPoints(),
                 StrahlerOrder(),
                 SimplifyVisvalingam(),
                 LeftRightDGO(),
                 BinaryClosing(),
                 MatchPolygonWithNearestCentroid(),
                 ProjectPointsAlongMostImportantLine(),
                 MatchPolygonWithMostImportantLine(),
                 LeftRightBox(),
                 SafePolygonIntersection(),
                 MeasureDGO(),
                 IdentifyNetworkNodes(),
                 SelectConnectedComponents(),
                 MeasureLinesFromOutlet() ]
        try:
          from shapelish import *
          algs.append(FastVariableDistanceBuffer())
          algs.append(FastFixedDistanceBuffer())
        except ImportError:
          pass
        self.algs.extend(algs)