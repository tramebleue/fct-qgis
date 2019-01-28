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


from qgis.PyQt.QtCore import ( # pylint:disable=no-name-in-module
    QCoreApplication
)

class AlgorithmMetadata(object):
    """
    Base class for storing algorithm metadata
    in a separate YAML (.yml) file next to the .py source file.
    """

    # pylint:disable=no-member,missing-docstring

    @staticmethod
    def read(sourcefile, algname):
        with open(os.path.join(os.path.dirname(sourcefile), algname + '.yml')) as stream:
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
        return self.METADATA['groupId']

    def group(self):
        return self.tr(self.METADATA['group'])

    def helpString(self):
        return self.METADATA.get('helpString')

    def helpUrl(self):
        return self.METADATA.get('helpUrl')

    def shortDescription(self):
        return self.renderHelpText(self.METADATA.get('shortDescription', self.__doc__))

    def shortHelpString(self):
        return self.METADATA.get('shortHelpString')

    def tags(self):
        return [self.tr(tag) for tag in self.METADATA.get('tags', [])]

    def renderHelpText(self, text): #pylint:disable=no-self-use
        return text.replace('\n', '<br/>') if text else ''
