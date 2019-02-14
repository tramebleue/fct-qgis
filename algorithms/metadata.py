# -*- coding: utf-8 -*-

"""
AlgorithmMetadata

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import os
import yaml


from qgis.PyQt.QtCore import ( # pylint:disable=import-error,no-name-in-module
    QCoreApplication
)

DOC_URL = 'https://tramebleue.github.io/fct/algorithms/%s'

class AlgorithmMetadata(object):
    """
    Base class for storing algorithm metadata
    in a separate YAML (.yml) file next to the .py source file.
    """

    # pylint:disable=no-member,missing-docstring

    @staticmethod
    def read(sourcefile, basename):

        with open(
            os.path.join(os.path.dirname(sourcefile), basename + '.yml'),
            encoding='utf-8') as stream:

            return yaml.load(stream)

    def createInstance(self):
        return type(self)()

    def tr(self, string, context=''): #pylint:disable=no-self-use,invalid-name

        if context == '':
            context = 'FluvialCorridorToolbox'

        return QCoreApplication.translate(context, string)

    def name(self):
        return type(self).__name__.lower()

    def displayName(self):
        name = self.METADATA.get('displayName')
        return self.tr(name) if name else None

    def groupId(self):
        return self.METADATA['group']

    def group(self):
        return self.provider().groupDisplayName(self.groupId())

    def helpString(self):
        return self.METADATA.get('description')

    def helpUrl(self):
        return self.METADATA.get('helpUrl', DOC_URL % type(self).__name__)

    def shortDescription(self):
        return self.renderHelpText(self.METADATA.get('summary', self.__doc__))

    def shortHelpString(self):
        return self.METADATA.get('shortHelpString')

    def tags(self):
        return [self.tr(tag) for tag in self.METADATA.get('tags', [])]

    def renderHelpText(self, text): #pylint:disable=no-self-use
        return '<br/>'.join([s.lstrip() for s in text.split('\n')]) if text else ''
