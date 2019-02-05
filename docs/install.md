# Getting started

## Install Dependencies

The recommended way to install dependencies is using  `pip`.
`pip` is installed by default in recent versions of Python.

    pip3 install -r requirements.txt

## Install Plugin On Windows

On Windows, copy the directory `plugin` to your local plugin folder,
and rename it to `FluvialCorridorToolbox`.

## Install on Linux or Mac OS

On Linux or Mac OS, you can use the provided Makefile.

The following command will install the plugin in your local plugin folder :

    make

If needed, you can set `QGIS_USER_DIR`
to point to your local folder where QGis stores installed plugins.

	make QGIS_USER_DIR=/path/to/qgis/plugin/folder

On Linux, the default is `$(HOME)/.local/share/QGIS/QGIS3/profiles/default`.

## Building Cython Extensions

You can build and install the Cython extension for Terrain Analysis algorithms
with the following command :

    make extensions

Alternatively, you can cd into the `cython` directory and type :

	python3 setup.py install --install-platlib=/path/to/plugin/lib

where `/path/to/plugin` is the installation folder for the FCT plugin,
for example `$QGIS_USER_DIR/FluvialCorridorToolbox`.