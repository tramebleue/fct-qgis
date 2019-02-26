from setuptools import setup, find_packages
from distutils.extension import Extension
import numpy
from Cython.Build import cythonize


extensions = [

    Extension(
        'fct.lib.terrain_analysis',
        ['cython/terrain/terrain_analysis.pyx'],
        language='c++',
        include_dirs=[numpy.get_include()]
    )

]

setup(
    name='fct',
    version='0.1',
    packages=find_packages(),
    ext_modules=cythonize(extensions),
    include_package_data=True,
    install_requires=[
        'Click>=7.0',
        'scipy>=1.2.0',
        'plotly>=3.3'
    ],
    entry_points='''
[console_scripts]
autodoc=fct.cli.autodoc:autodoc
fct=fct.cli.algorithms:fct
fcw=fct.cli.algorithms:workflows
    ''',
)
