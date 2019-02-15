# -*- coding: utf-8 -*-

"""
Command Line Interface

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import sys
import os

if __name__ == '__main__':

    sys.path.append(os.path.expandvars('$QGIS_PREFIX/share/qgis/python/plugins'))
    sys.path.append(os.path.expandvars('$HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins'))

    from FluvialCorridorToolbox.FluvialCorridorToolbox import FluvialCorridorToolboxProvider
    from .commands import AlgorithmProviderCommands

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()

    cli = AlgorithmProviderCommands('fct', provider)
    cli()
