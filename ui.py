from PyQt4.QtGui import QComboBox, QSpacerItem
from PyQt4.QtGui import QVBoxLayout, QPushButton, QWidget

from qgis.core import QgsMapLayerRegistry

from processing.core.parameters import ParameterVector
from processing.tools import dataobjects
from processing.gui.ParametersPanel import ParametersPanel
from processing.gui.AlgorithmDialog import AlgorithmDialog, AlgorithmDialogBase
from processing.modeler.ModelerParametersDialog import ModelerParametersDialog

from processing.gui.MultipleInputPanel import MultipleInputPanel
from .parameters import ParameterTableMultipleField


class FluvialToolboxParametersPanel(ParametersPanel):

    def __init__(self, parent, alg):

        # super(FluvialToolboxParametersPanel, self).__init__(parent, alg)
        ParametersPanel.__init__(self, parent, alg)
        # self.setupUi(self)

        # item = self.layoutMain.itemAt(self.layoutMain.count() - 1)
        # if isinstance(item, QSpacerItem):
        #     self.layoutMain.removeItem(item)
        #     item = None

    def getWidgetFromParameter(self, param):
        
        if isinstance(param, ParameterTableMultipleField):
        
            if param.parent in self.dependentItems:
                items = self.dependentItems[param.parent]
            else:
                items = []
                self.dependentItems[param.parent] = items
            items.append(param.name)
            
            parent = self.alg.getParameterFromName(param.parent)
            options = []
            
            if isinstance(parent, ParameterVector):
                layers = dataobjects.getVectorLayers(parent.shapetype)
            else:
                layers = dataobjects.getTables()
            if len(layers) > 0:
                options = self.getFields(layers[0], param.datatype)
            
            return MultipleInputPanel(options)

        else:
            # super(self).getWidgetFromParameter(param)
            return ParametersPanel.getWidgetFromParameter(self, param)

    def updateDependentFields(self):

        sender = self.sender()
        if not isinstance(sender, QComboBox):
            return
        if sender.name not in self.dependentItems:
            return
        
        layer = sender.itemData(sender.currentIndex())
        children = self.dependentItems[sender.name]
        
        for child in children:

            widget = self.valueItems[child]
            
            if isinstance(widget, MultipleInputPanel):
                
                options = self.getFields(layer, self.alg.getParameterFromName(child).datatype)
                widget.updateForOptions(options)

            else:

                widget.clear()
                if self.alg.getParameterFromName(child).optional:
                    widget.addItem(self.tr('[not set]'))
                widget.addItems(self.getFields(layer,
                                               self.alg.getParameterFromName(child).datatype))

    def somethingDependsOnThisParameter(self, parent):

        for param in self.alg.parameters:
            if isinstance(param, ParameterTableMultipleField):
                if param.parent == parent.name:
                    return True
        
        # return super(FluvialToolboxModelerParametersDialog, self).somethingDependsOnThisParameter(parent)
        return False


class FluvialToolboxParametersDialog(AlgorithmDialog):

    def __init__(self, alg):

        AlgorithmDialogBase.__init__(self, alg)

        self.alg = alg

        self.mainWidget = FluvialToolboxParametersPanel(self, alg)
        self.setMainWidget()

        cornerWidget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 5)
        self.tabWidget.setStyleSheet("QTabBar::tab { height: 30px; }")
        runAsBatchButton = QPushButton(self.tr("Run as batch process..."))
        runAsBatchButton.clicked.connect(self.runAsBatch)
        layout.addWidget(runAsBatchButton)
        cornerWidget.setLayout(layout)
        self.tabWidget.setCornerWidget(cornerWidget)

        QgsMapLayerRegistry.instance().layerWasAdded.connect(self.mainWidget.layerAdded)
        QgsMapLayerRegistry.instance().layersWillBeRemoved.connect(self.mainWidget.layersWillBeRemoved)

    def setParamValue(self, param, widget, alg=None):
        if isinstance(param, ParameterTableMultipleField):
            return param.setValue(widget.selectedoptions)
        else:
            # return super(FluvialToolboxParametersDialog, self).setParamValue(param, widget, alg)
            return AlgorithmDialog.setParamValue(self, param, widget, alg)


class FluvialToolboxModelerParametersDialog(ModelerParametersDialog):

    def __init__(self, alg, model, algName=None):
        
        # super(FluvialToolboxModelerParametersDialog, self).__init__(alg, model, algName)
        ModelerParametersDialog.__init__(self, alg, model, algName)

        paramsLayout = self.paramPanel.layout()
        item = paramsLayout.itemAt(paramsLayout.count() - 1)
        if isinstance(item, QSpacerItem):
            paramsLayout.removeItem(item)
            item = None

    def getWidgetFromParameter(self, param):

        if isinstance(param, ParameterTableMultipleField):
            options = []
            return MultipleInputPanel(options)
        else:
            # return super(FluvialToolboxModelerParametersDialog, self).getWidgetFromParameter(param)
            return ModelerParametersDialog.getWidgetFromParameter(self, param)

    def setPreviousValues(self):
        
        # super(FluvialToolboxModelerParametersDialog, self).setPreviousValues()
        ModelerParametersDialog.setPreviousValues(self)
        
        if self._algName is not None:
            alg = self.model.algs[self._algName]
            for param in alg.algorithm.parameters:
                if isinstance(param, ParameterTableMultipleField):
                    widget = self.valueItems[param.name]
                    value = alg.params[param.name]
                    if isinstance(value, unicode):
                        # convert to list because of ModelerAlgorithme.resolveValue behavior with lists
                        value = eval(value)
                    widget.setSelectedItems(value)

    def setParamValue(self, alg, param, widget):

        if isinstance(param, ParameterTableMultipleField):
            # convert to unicode because of ModelerAlgorithme.resolveValue behavior with lists
            alg.params[param.name] = unicode(widget.selectedoptions)
            return True
        else:
            # return super(FluvialToolboxModelerParametersDialog, self).setParamValue(alg, param, widget)
            return ModelerParametersDialog.setParamValue(self, alg, param, widget)