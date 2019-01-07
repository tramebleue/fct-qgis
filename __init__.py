# -*- coding: utf-8 -*-

from .FluvialCorridorToolbox import FluvialCorridorToolboxPlugin

def classFactory(iface):

    return FluvialCorridorToolboxPlugin(iface)