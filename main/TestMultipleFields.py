from qgis.core import QGis, QgsFeature, QgsGeometry, QgsPoint, QgsVector, QgsSpatialIndex, QgsFields, QgsField, QgsWKBTypes
from qgis.core import QgsVectorLayer
from qgis.core import QgsFeatureRequest, QgsExpression
from PyQt4.QtCore import QVariant
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools import dataobjects, vector
from processing.core.ProcessingLog import ProcessingLog

from ..parameters import ParameterTableMultipleField
from ..ui import FluvialToolboxParametersDialog, FluvialToolboxModelerParametersDialog

class TestMultipleFields(GeoAlgorithm):

    INPUT_LAYER = 'INPUT_LAYER'
    INPUT_FIELDS = 'INPUT_FIELDS'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Test Multiple Fields')
        self.group, self.i18n_group = self.trAlgorithm('Tests')

        self.addParameter(ParameterVector(self.INPUT_LAYER,
                                          self.tr('Input Layer'), [ParameterVector.VECTOR_TYPE_ANY]))

        self.addParameter(ParameterTableMultipleField(self.INPUT_FIELDS,
                                                       self.tr('Input Fields'),
                                                       parent=self.INPUT_LAYER,
                                                       datatype=ParameterTableMultipleField.DATA_TYPE_ANY))

    def processAlgorithm(self, progress):

        layer = self.getParameterValue(self.INPUT_LAYER)
        fields = self.getParameterValue(self.INPUT_FIELDS)

        ProcessingLog.addToLog(ProcessingLog.LOG_INFO, "%s : %s %s" % (layer, fields, type(fields)))


    def getCustomParametersDialog(self):
        return FluvialToolboxParametersDialog(self)

    def getCustomModelerParametersDialog(self, modelAlg, algName=None):
        return FluvialToolboxParametersDialog(self, modelAlg, algName)