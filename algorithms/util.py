# -*- coding: utf-8 -*-

"""
Helper functions for processing algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFields
)

def asQgsFields(*fields):
    """ Turn list-of-fields into QgsFields object
    """

    out = QgsFields()
    for field in fields:
        out.append(field)
    return out
