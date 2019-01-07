import os
import yaml
from qgis.PyQt.QtCore import QCoreApplication

class AlgorithmMetadata(object):

    @classmethod
    def read(cls, file, algname):
        with open(os.path.join(os.path.dirname(file), algname + '.yml')) as fp:
            return yaml.load(fp)

    def tr(self, string, context=''):
        
        if context == '':
            context = 'FluvialCorridorToolbox'

        return QCoreApplication.translate(context, string)

    def name(self):
        return type(self).__name__.lower()

    def displayName(self):
        dn = self.METADATA.get('displayName')
        return self.tr(dn) if dn else None

    def groupId(self):
        return self.METADATA['groupId']

    def group(self):
        return self.tr(self.METADATA['group'])

    def helpString(self):
        return self.METADATA.get('helpString')

    def helpUrl(self):
        return self.METADATA.get('helpUrl')

    def shortDescription(self):
        return self.METADATA.get('shortDescription', self.__doc__)

    def shortHelpString(self):
        return self.METADATA.get('shortHelpString')

    def tags(self):
        return map(self.tr, self.METADATA.get('tags', []))

    def createInstance(self):
        return type(self)()