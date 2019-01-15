# -*- coding: utf-8 -*-

"""
Build cython modules

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from distutils.core import setup
from distutils.extension import Extension
import numpy
from Cython.Build import cythonize


extensions = [

    Extension(
        'terrain_analysis',
        ['terrain/terrain_analysis.pyx'],
        language='c++',
        include_dirs=[numpy.get_include()]
    )

]

setup(
    name="terrain_analysis",
    ext_modules=cythonize(extensions)
)
