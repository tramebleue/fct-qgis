# -*- coding: utf-8 -*-

"""
RasterizeStreamNetwork

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

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsProcessingModelAlgorithm
)

from ..metadata import AlgorithmMetadata

class RasterizeStreamNetwork(AlgorithmMetadata, QgsProcessingModelAlgorithm):
    """
    Create a new raster having the same dimension as the input raster template,
    and assign the stream id to matching stream cells.
    You must specify an ID field with values > 0.
    Non-stream cells will be assigned 0, the no-data value of the returned raster.
    """

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.METADATA = AlgorithmMetadata.read(__file__, type(self).__name__)
        self.fromFile(os.path.join(os.path.dirname(__file__), type(self).__name__ + '.model3'))
