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
        self.provider = FluvialCorridorToolboxProvider()
        self.wfprovider = FluvialCorridorWorkflowsProvider()

    def initGui(self):

        QgsApplication.processingRegistry().addProvider(self.provider)
        QgsApplication.processingRegistry().addProvider(self.wfprovider)

    def unload(self):

        QgsApplication.processingRegistry().removeProvider(self.provider)
        QgsApplication.processingRegistry().removeProvider(self.wfprovider)

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


class FluvialCorridorToolboxProvider(QgsProcessingProvider):

    METADATA = AlgorithmMetadata.read(__file__, 'FluvialCorridorToolbox')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = {g['id']: g['displayName'] for g in self.METADATA['groups']}

    def id(self):
        return 'fct'

    def name(self):
        return 'Fluvial Corridor Toolbox'
    
    def longName(self):
        return 'Fluvial Corridor Toolbox'

    def load(self):
        
        ProcessingConfig.addSetting(
            Setting(
                "Fluvial Corridor Toolbox",
                'FCT_ACTIVATE_CYTHON',
                self.tr('Activate Cython Extensions'), True))

        ProcessingConfig.readSettings()
        self.refreshAlgorithms()

        return True

    def unload(self):
        ProcessingConfig.removeSetting('FCT_ACTIVATE_CYTHON')

    def groupDisplayName(self, group):

        return self.groups[group]

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), 'images/tbxIcon.png'))

    def loadAlgorithms(self):

        alg_dir = os.path.join(os.path.dirname(__file__), 'algorithms')

        groups = sorted([
            g for g in os.listdir(alg_dir)
            if not g.startswith('__') and os.path.isdir(os.path.join(alg_dir, g))
        ])

        for group in groups:

            module = importlib.reload(importlib.import_module('..algorithms.' + group, __name__))
            count = 0

            for key in dir(module):

                obj = getattr(module, key)

                if callable(obj):
                    algorithm = obj()
                    if isinstance(algorithm, QgsProcessingAlgorithm):
                        self.addAlgorithm(algorithm)
                        count += 1


class FluvialCorridorWorkflowsProvider(QgsProcessingProvider):

    METADATA = AlgorithmMetadata.read(__file__, 'FluvialCorridorWorkflows')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = {g['id']: g['displayName'] for g in self.METADATA['groups']}

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

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), 'images/wfIcon.png'))

    def loadAlgorithms(self):

        alg_dir = os.path.join(os.path.dirname(__file__), 'workflows')

        groups = sorted([
            g for g in os.listdir(alg_dir)
            if not g.startswith('__') and os.path.isdir(os.path.join(alg_dir, g))
        ])

        for group in groups:

            module = importlib.reload(importlib.import_module('..workflows.' + group, __name__))
            count = 0

            for key in dir(module):

                obj = getattr(module, key)

                if callable(obj):
                    algorithm = obj()
                    if isinstance(algorithm, QgsProcessingAlgorithm):
                        self.addAlgorithm(algorithm)
                        count += 1

PROVIDERS = [
    ('algorithms', FluvialCorridorToolboxProvider),
    ('workflows', FluvialCorridorWorkflowsProvider)
]
