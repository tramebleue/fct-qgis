import os

from PyQt4.QtGui import QDialog
from PickLayerDialogBase import Ui_PickLayerDialogBase as PickLayerDialogBase

# FORM_CLASS, _ = uic.loadUiType(os.path.join(
#     os.path.dirname(__file__), 'pick_layer_dialog.ui'))


class PickLayerDialog(QDialog, PickLayerDialogBase):

    def __init__(self, parent=None, filters=None):
        """Constructor."""
        super(PickLayerDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
        # if filters is not None:
        #     self.layer_combo.setFilters(filters)