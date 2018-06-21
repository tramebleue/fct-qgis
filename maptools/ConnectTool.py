# coding: utf-8

from qgis.core import QgsGeometry, QgsFeature, QgsFeatureRequest
from qgis.gui import QgsMapToolIdentifyFeature, QgsMessageBar
from qgis.utils import iface
from PyQt4.QtGui import QCursor, QPixmap
from PyQt4.QtCore import Qt, SIGNAL


class ConnectTool(QgsMapToolIdentifyFeature):

    def __init__(self, canvas):

        super(ConnectTool, self).__init__(canvas)

        self.canvas = canvas
        self.cursor = QCursor(Qt.CrossCursor)
        self.from_node_field = 'NODE_A'
        self.to_node_field = 'NODE_B'
        self.target_feature_id = None

    @classmethod
    def initGui(cls, plugin):

        icon_path = ':/plugins/FluvialToolbox/icon.png'

        instance = ConnectTool(iface.mapCanvas())
        
        action = plugin.add_action(
                icon_path,
                plugin.tr('Connect'),
                callback=lambda: iface.mapCanvas().setMapTool(instance),
                parent=iface.mainWindow())
        
        action.setCheckable(False)
        instance.setAction(action)

        return instance

    def setLayer(self, layer):

        super(ConnectTool, self).setLayer(layer)

        if layer:
            self.layer = layer
            self.from_node_field_idx = layer.fieldNameIndex(self.from_node_field)
            self.to_node_field_idx = layer.fieldNameIndex(self.to_node_field)

    def activate(self):

        self.ancient_cursor = self.canvas.cursor()
        self.canvas.setCursor(self.cursor)
        self.doConnect = False
        self.setLayer(self.canvas.currentLayer())
        self.connect(self, SIGNAL('featureIdentified(QgsFeature)'), self.processFeature)

    def deactivate(self):

        self.canvas.setCursor(self.ancient_cursor)
        self.disconnect(self, SIGNAL('featureIdentified(QgsFeature)'), self.processFeature)

    def canvasReleaseEvent(self, mouseEvent):

        if mouseEvent.modifiers() & Qt.ControlModifier:
            self.doConnect = True
        else:
            self.doConnect = False

        super(ConnectTool, self).canvasReleaseEvent(mouseEvent)

    def processFeature(self, feature):

        layer = self.layer

        if self.doConnect and self.target_feature_id is not None:

            layer.startEditing()

            target_feature = layer.getFeatures(QgsFeatureRequest(self.target_feature_id)).next()

            connect_node = feature.attribute(self.from_node_field)
            target_feature.setAttribute(self.to_node_field_idx, connect_node)
            layer.updateFeature(target_feature)
        
            layer.commitChanges()

            iface.messageBar().pushMessage(
                "Connect Tool",
                "Selected line has been connected to node %s" % connect_node,
                QgsMessageBar.INFO,
                2
            )

        else:
            
            layer.removeSelection()
            layer.select(feature.id())
            self.target_feature_id = feature.id()


