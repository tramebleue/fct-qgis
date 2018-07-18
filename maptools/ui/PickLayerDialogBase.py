# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'maptools/ui/pick_layer_dialog.ui'
#
# Created by: PyQt4 UI code generator 4.11.4
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_PickLayerDialogBase(object):
    def setupUi(self, PickLayerDialogBase):
        PickLayerDialogBase.setObjectName(_fromUtf8("PickLayerDialogBase"))
        PickLayerDialogBase.resize(400, 300)
        self.layer_combo = gui.QgsMapLayerComboBox(PickLayerDialogBase)
        self.layer_combo.setGeometry(QtCore.QRect(30, 30, 341, 32))
        self.layer_combo.setFilters(gui.QgsMapLayerProxyModel.PointLayer)
        self.layer_combo.setObjectName(_fromUtf8("layer_combo"))
        self.button_box = QtGui.QDialogButtonBox(PickLayerDialogBase)
        self.button_box.setGeometry(QtCore.QRect(30, 240, 341, 32))
        self.button_box.setOrientation(QtCore.Qt.Horizontal)
        self.button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.button_box.setObjectName(_fromUtf8("button_box"))

        self.retranslateUi(PickLayerDialogBase)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("accepted()")), PickLayerDialogBase.accept)
        QtCore.QObject.connect(self.button_box, QtCore.SIGNAL(_fromUtf8("rejected()")), PickLayerDialogBase.reject)
        QtCore.QMetaObject.connectSlotsByName(PickLayerDialogBase)

    def retranslateUi(self, PickLayerDialogBase):
        PickLayerDialogBase.setWindowTitle(_translate("PickLayerDialogBase", "Choose a Target Layer", None))

from qgis import gui
