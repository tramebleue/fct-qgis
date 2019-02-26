# -*- coding: utf-8 -*-

"""
Fluvial Corridor Toolbox Entry Point

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
import importlib

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon

from qgis.core import ( # pylint: disable=import-error,no-name-in-module
    QgsApplication,
    QgsProcessingProvider,
    QgsProcessingAlgorithm
)

from processing.core.ProcessingConfig import ProcessingConfig, Setting

from .algorithms.metadata import AlgorithmMetadata

class FluvialCorridorToolboxPlugin:

    def __init__(self, iface):

        # self.iface = iface
        self.providers = [cls() for cls in PROVIDERS]

    def initGui(self):

        for provider in self.providers:
            QgsApplication.processingRegistry().addProvider(provider)

    def unload(self):

        for provider in self.providers:
            QgsApplication.processingRegistry().removeProvider(provider)

    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('FluvialCorridorToolbox', message)

class FluvialCorridorBaseProvider(QgsProcessingProvider):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = {g['id']: g['displayName'] for g in self.METADATA['groups']}

    def groupDisplayName(self, group):

        return self.groups[group]

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), self.ICON))

    def loadAlgorithms(self):

        alg_dir = os.path.join(os.path.dirname(__file__), self.SOURCE_FOLDER)

        groups = sorted([
            g for g in os.listdir(alg_dir)
            if not g.startswith('__') and os.path.isdir(os.path.join(alg_dir, g))
        ])

        for group in groups:

            module = importlib.reload(importlib.import_module(f'..{self.SOURCE_FOLDER}.{group}', __name__))
            count = 0

            for key in dir(module):

                obj = getattr(module, key)

                if callable(obj):
                    algorithm = obj()
                    if isinstance(algorithm, QgsProcessingAlgorithm):
                        self.addAlgorithm(algorithm)
                        count += 1

class FluvialCorridorToolboxProvider(FluvialCorridorBaseProvider):

    METADATA = AlgorithmMetadata.read(__file__, 'FluvialCorridorToolbox')
    SOURCE_FOLDER = 'algorithms'
    ICON = 'images/tbxIcon.png'
    CYTHON_SETTING = 'FCT_ACTIVATE_CYTHON'

    def id(self):
        return 'fct'

    def name(self):
        return 'Fluvial Corridor Toolbox'
    
    def longName(self):
        return 'Fluvial Corridor Toolbox'

    def load(self):
        
        ProcessingConfig.addSetting(
            Setting(
                self.name(),
                self.CYTHON_SETTING,
                self.tr('Activate Cython Extensions'),
                True))

        ProcessingConfig.readSettings()
        self.refreshAlgorithms()

        return True

    def unload(self):
        ProcessingConfig.removeSetting(self.CYTHON_SETTING)


class FluvialCorridorWorkflowsProvider(FluvialCorridorBaseProvider):

    METADATA = AlgorithmMetadata.read(__file__, 'FluvialCorridorWorkflows')
    SOURCE_FOLDER = 'workflows'
    ICON = 'images/wfIcon.png'

    def id(self):
        return 'fcw'

    def name(self):
        return 'Fluvial Corridor Workflows'
    
    def longName(self):
        return 'Fluvial Corridor Workflows'

    def load(self):
        self.refreshAlgorithms()
        return True

    def groupDisplayName(self, group):

        return self.groups[group]


PROVIDERS = [
    FluvialCorridorToolboxProvider,
    FluvialCorridorWorkflowsProvider
]
