# -*- coding: utf-8 -*-

"""
DetrendDEM

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

# def DetrendDEM():
#     algorithm = QgsProcessingModelAlgorithm()
#     algorithm.fromFile(os.path.join(os.path.dirname(__file__), 'DetrendDEM.model3'))
#     return algorithm

class DetrendDEM(AlgorithmMetadata, QgsProcessingModelAlgorithm):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.METADATA = AlgorithmMetadata.read(__file__, type(self).__name__)
        self.fromFile(os.path.join(os.path.dirname(__file__), type(self).__name__ + '.model3'))
