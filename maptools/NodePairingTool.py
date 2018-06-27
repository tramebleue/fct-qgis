# coding: utf-8

from qgis.core import QgsGeometry, QgsFeature, QgsFeatureRequest, QgsSpatialIndex
from qgis.gui import QgsMapTool, QgsMessageBar
from qgis.utils import iface
from PyQt4.QtGui import QCursor, QPixmap
from PyQt4.QtCore import Qt, SIGNAL
from collections import defaultdict
from ui import PickLayerDialog


class NodePairingTool(QgsMapTool):

    def __init__(self, canvas):

        super(NodePairingTool, self).__init__(canvas)

        self.canvas = canvas
        self.cursor = QCursor(Qt.CrossCursor)

        self.dialog = PickLayerDialog(iface.mainWindow())
        self.dialog.accepted.connect(self.setupTool)

        self.source = None
        self.source_fid = None
        self.source_index = None
        self.target = None
        self.target_index = None

    @classmethod
    def initGui(cls, plugin):

        icon_path = ':/plugins/FluvialToolbox/icon.png'

        instance = NodePairingTool(iface.mapCanvas())
        
        action = plugin.add_action(
                icon_path,
                plugin.tr('Node Pairing'),
                callback=instance.dialog.show,
                parent=iface.mainWindow())
        
        action.setCheckable(False)
        instance.setAction(action)

        action = plugin.add_action(
                icon_path,
                plugin.tr('Delete Pair'),
                callback=instance.deletePair,
                parent=iface.mainWindow(),
                enabled_flag=False)

        instance.setDeletePairAction(action)

        return instance

    def setupTool(self):

        self.setSourceLayer(iface.mapCanvas().currentLayer())
        self.setTargetLayer(self.dialog.layer_combo.currentLayer())
        iface.mapCanvas().setMapTool(self)

    def build_link_index(self, layer):

        index = defaultdict(list)

        for feature in layer.getFeatures():
            target_id = feature.attribute('TGID')
            index[target_id].append(feature.id())

        self.link_index = index

    def setSourceLayer(self, layer):

        self.source = layer
        self.source_index = QgsSpatialIndex(layer.getFeatures())
        self.build_link_index(layer)
        self.tgid_field_idx = layer.fieldNameIndex('TGID')
        self.tx_field_idx = layer.fieldNameIndex('TX')
        self.ty_field_idx = layer.fieldNameIndex('TY')

    def setTargetLayer(self, layer):

        self.target = layer
        self.target_index = QgsSpatialIndex(layer.getFeatures())

    def activate(self):

        self.ancient_cursor = self.canvas.cursor()
        self.canvas.setCursor(self.cursor)
        # self.setSourceLayer(iface.mapCanvas().currentLayer())
        # iface.currentLayerChanged.connect(self.setTargetLayer)

        if self.deletePairAction:
            self.deletePairAction.setEnabled(True)

    def deactivate(self):

        self.canvas.setCursor(self.ancient_cursor)
        # iface.currentLayerChanged.disconnect(self.setTargetLayer)
        # del self.source_index
        # del self.target_index

        if self.deletePairAction:
            self.deletePairAction.setEnabled(False)

    def canvasReleaseEvent(self, mouseEvent):

        if mouseEvent.modifiers() & Qt.ControlModifier:

            self.linkToTargetFeature(mouseEvent)

        elif mouseEvent.modifiers() & Qt.AltModifier:

            self.selectSourceFeature(mouseEvent)
            self.deletePair()

        else:

            self.selectSourceFeature(mouseEvent)
            

    def selectSourceFeature(self, mouseEvent):

        point = self.toLayerCoordinates(self.source, mouseEvent.pos())
        
        for fid in self.source_index.nearestNeighbor(point, 1):

            self.source_fid = fid

        self.source.removeSelection()
        self.source.select(self.source_fid)

    def setDeletePairAction(self, action):

        self.deletePairAction = action

    def deletePair(self):

        if self.source_fid is not None:

            iface.messageBar().pushMessage(
                "Node Pairing Tool",
                "Delete pair from node %s" % self.source_fid,
                QgsMessageBar.INFO,
                2
            )

            self.source.startEditing()

            feature = self.source.getFeatures(QgsFeatureRequest(self.source_fid)).next()
            feature.setAttribute(self.tgid_field_idx, None)
            feature.setAttribute(self.tx_field_idx, None)
            feature.setAttribute(self.ty_field_idx, None)
            self.source.updateFeature(feature)

            self.source.commitChanges()

    def linkToTargetFeature(self, mouseEvent):

        if self.source_fid is None:
            return

        feature = self.source.getFeatures(QgsFeatureRequest(self.source_fid)).next()

        point = self.toLayerCoordinates(self.target, mouseEvent.pos())

        for fid in self.target_index.nearestNeighbor(point, 1):
            target_feature = self.target.getFeatures(QgsFeatureRequest(fid)).next()

        if target_feature is not None:

            target_gid = target_feature.attribute('GID')
            p = target_feature.geometry().asPoint()

            iface.messageBar().pushMessage(
                "Node Pairing Tool",
                "Link to node %s" % target_gid,
                QgsMessageBar.INFO,
                2
            )

            self.source.startEditing()

            if not (mouseEvent.modifiers() & Qt.ShiftModifier):

                for fid in self.link_index[target_gid]:

                    other_feature = self.source.getFeatures(QgsFeatureRequest(fid)).next()
                    other_feature.setAttribute(self.tgid_field_idx, None)
                    other_feature.setAttribute(self.tx_field_idx, None)
                    other_feature.setAttribute(self.ty_field_idx, None)
                    self.source.updateFeature(other_feature)

                self.link_index[target_gid] = list()
            
            feature.setAttribute(self.tgid_field_idx, target_gid)
            feature.setAttribute(self.tx_field_idx, p.x())
            feature.setAttribute(self.ty_field_idx, p.y())
            self.source.updateFeature(feature)

            self.link_index[target_gid].append(feature.id())
            
            self.source.commitChanges()





        



