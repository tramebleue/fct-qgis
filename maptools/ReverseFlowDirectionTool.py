# coding: utf-8

from qgis.core import QgsGeometry, QgsFeature
from qgis.gui import QgsMapToolIdentifyFeature
from PyQt4.QtGui import QCursor, QPixmap
from PyQt4.QtCore import Qt, SIGNAL

def reversePolyline(geometry):

        if geometry.isMultipart():
            
            polylines = list()
            for polyline in geometry.asMultiPolyline():
                polyline.reverse()
                polylines.append(polyline)
            polylines.reverse()
            return QgsGeometry.fromMultiPolyline(polylines)

        else:
            
            polyline = geometry.asPolyline()
            polyline.reverse()
            return QgsGeometry.fromPolyline(polyline)

class ReverseFlowDirectionTool(QgsMapToolIdentifyFeature):

    def __init__(self, canvas, layer):

        super(ReverseFlowDirectionTool, self).__init__(canvas, layer)

        self.canvas = canvas
        self.cursor = QCursor(Qt.CrossCursor)
        self.from_node_field = 'NODE_A'
        self.to_node_field = 'NODE_B'
        if layer is not None:
            self.setLayer(layer)

    def setLayer(self, layer):

        super(ReverseFlowDirectionTool, self).setLayer(layer)
        self.layer = layer
        self.from_node_field_idx = layer.fieldNameIndex(self.from_node_field)
        self.to_node_field_idx = layer.fieldNameIndex(self.to_node_field)

    def activate(self):

        self.ancient_cursor = self.canvas.cursor()
        self.canvas.setCursor(self.cursor)
        self.doSelect = False
        self.setLayer(self.canvas.currentLayer())
        self.connect(self, SIGNAL('featureIdentified(QgsFeature)'), self.processFeature)

    def deactivate(self):

        self.canvas.setCursor(self.ancient_cursor)
        self.disconnect(self, SIGNAL('featureIdentified(QgsFeature)'), self.processFeature)

    def canvasReleaseEvent(self, mouseEvent):

        if mouseEvent.modifiers() & Qt.ControlModifier:
            self.doSelect = True
        else:
            self.doSelect = False

        super(ReverseFlowDirectionTool, self).canvasReleaseEvent(mouseEvent)

    def processFeature(self, feature):

        self.layer.startEditing()

        from_node = feature.attribute(self.from_node_field)
        to_node = feature.attribute(self.to_node_field)
        geometry = reversePolyline(feature.geometry())

        self.layer.changeAttributeValue(feature.id(), self.from_node_field_idx, to_node, from_node)
        self.layer.changeAttributeValue(feature.id(), self.to_node_field_idx, from_node, to_node)
        self.layer.changeGeometry(feature.id(), geometry)
        
        self.layer.commitChanges()

        if self.doSelect:
            self.layer.select(feature.id())


