# -*- coding: utf-8 -*-

"""
Graph Algorithm Helpers

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict

def create_link_index(adjacency, key):
    """ Index: key -> list of link corresponding to key
    """

    index = defaultdict(list)

    for link in adjacency:
        k = key(link)
        index[k].append(link)

    return index
