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
        self.fictif_field = 'fictif'
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
            self.fictif_field_idx = layer.fieldNameIndex(self.fictif_field)

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

        if self.doConnect:

            if self.target_feature_id is not None:

                target_feature = layer.getFeatures(QgsFeatureRequest(self.target_feature_id)).next()

                a = target_feature.geometry().interpolate(target_feature.geometry().length()).asPoint()
                b = feature.geometry().interpolate(0.0).asPoint()

                layer.startEditing()

                connect_node = feature.attribute(self.from_node_field)
                # target_feature.setAttribute(self.to_node_field_idx, connect_node)
                # layer.updateFeature(target_feature)

                new_feature = QgsFeature()
                attrs = target_feature.attributes()
                attrs[self.from_node_field_idx] = target_feature.attribute(self.to_node_field)
                attrs[self.to_node_field_idx] = connect_node
                attrs[self.fictif_field_idx] = 'Oui'
                new_feature.setAttributes(attrs)
                new_feature.setGeometry(QgsGeometry.fromPolyline([ a, b ]))
                layer.addFeature(new_feature)
            
                layer.commitChanges()

                iface.messageBar().pushMessage(
                    "Connect Tool",
                    "Selected line has been connected to node %s" % connect_node,
                    QgsMessageBar.INFO,
                    2
                )

            else:

                iface.messageBar().pushMessage(
                    "Connect Tool",
                    "Current selection is empty.",
                    QgsMessageBar.INFO,
                    2
                )

        else:
            
            layer.removeSelection()
            layer.select(feature.id())
            self.target_feature_id = feature.id()


