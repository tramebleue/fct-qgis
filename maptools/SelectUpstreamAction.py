from qgis.core import QgsFeatureRequest
from qgis.gui import QgsMessageBar
from qgis.utils import iface
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QProgressBar, QAction, QIcon

class SelectUpstreamAction(QAction):

    @classmethod
    def initGui(cls, plugin):

        icon_path = ':/plugins/FluvialToolbox/icon.png'

        action = SelectUpstreamAction(QIcon(icon_path), plugin.tr('Select Upstream'), iface.mainWindow())
        action.triggered.connect(action.execute)
        action.setEnabled(True)

        iface.addPluginToMenu(plugin.menu, action)
        plugin.toolbar.addAction(action)
        plugin.actions.append(action)

        return action

    def execute(self):

        layer = iface.activeLayer()
        from_node_field = 'NODE_A'
        to_node_field = 'NODE_B'

        # Check layer has field NODE_A and NODE_B

        if layer.fieldNameIndex(from_node_field) == -1 or layer.fieldNameIndex(to_node_field) == -1:
            
            iface.messageBar().pushMessage(
                "Invalid Layer",
                "Layer must have %s and %s fields." % (from_node_field, to_node_field),
                QgsMessageBar.WARNING,
                5
            )
            
            return

        to_node_index = dict()
        total = 100.0 / layer.featureCount()

        # iface.messageBar().pushMessage(
        #         "Select Upstream Tool",
        #         "Selecting connected segments. Please wait ...",
        #         QgsMessageBar.INFO,
        #         2
        #     )

        progressMessageBar = iface.messageBar().createMessage("Selecting connected segments ...")
        progress = QProgressBar()
        progress.setMaximum(100)
        progress.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        progressMessageBar.layout().addWidget(progress)
        iface.messageBar().pushWidget(progressMessageBar, iface.messageBar().INFO)

        for current, feature in enumerate(layer.getFeatures()):

            to_node = feature.attribute(to_node_field)
            if to_node_index.has_key(to_node):
                to_node_index[to_node].append(feature.id())
            else:
                to_node_index[to_node] = [ feature.id() ]

            progress.setValue(int(current * total))

        progress.setValue(100)

        process_stack = [ segment for segment in layer.selectedFeatures() ]
        selection = set()

        while process_stack:

            segment = process_stack.pop()
            selection.add(segment.id())
            from_node = segment.attribute(from_node_field)

            if to_node_index.has_key(from_node):
                q = QgsFeatureRequest().setFilterFids(to_node_index[from_node])
                for next_segment in layer.getFeatures(q):
                    # Prevent infinite loop
                    if not next_segment.id() in selection:
                        process_stack.append(next_segment)

        iface.messageBar().clearWidgets()

        iface.messageBar().pushMessage(
                "Select Upstream Tool",
                "Selected %d segments" % len(selection),
                QgsMessageBar.INFO,
                2
            )

        layer.setSelectedFeatures(list(selection))

