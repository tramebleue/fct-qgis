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

from qgis.core import ( # pylint:disable=import-error,no-name-in-module
    QgsFields
)

def asQgsFields(*fields):
    """ Turn list-of-fields into QgsFields object
    """

    out = QgsFields()
    for field in fields:
        out.append(field)
    return out

class FidGenerator(object):
    """ Generate a sequence of integers to be used as identifier
    """

    def __init__(self, start=0):
        self.x = start

    def __next__(self):
        self.x = self.x + 1
        return self.x

    @property
    def value(self):
        """ Current value of generator
        """
        return self.x

def createUniqueFieldName(name, fields):
    """
    Return a new name that is unique within `fields`
    """

    if fields.lookupField(name) == -1:
        return name

    if len(name) > 8:
        basename = name[:8]
    else:
        basename = name

    i = 0
    unique_name = basename + '_%d' % i

    while fields.lookupField(unique_name) > -1:
        i += 1
        unique_name = basename + '_%d' % i

    return unique_name

def appendUniqueField(field, fields):
    """
    Create a unique name for `field` within `fields`,
    and append `field` to `fields`.
    """

    if fields.lookupField(field.name()) > -1:
        field.setName(createUniqueFieldName(field.name(), fields))
    fields.append(field)
