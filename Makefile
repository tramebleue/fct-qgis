QGIS_PREFIX=/usr
QGIS_USER_DIR=$(HOME)/.local/share/QGIS/QGIS3/profiles/default
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/FluvialCorridorToolbox

default: install

plugin/resources.py: plugin/resources.qrc plugin/icon.png
	pyrcc5 -o plugin/resources.py plugin/resources.qrc

install: plugin/resources.py
	mkdir -p $(TARGET)
	cp -R plugin/* $(TARGET)
	echo Installed to $(TARGET)

extensions:
	make -C cython TARGET=$(TARGET) install

uninstall:
	echo Remove directory $(TARGET) ...
	rm -rf $(TARGET)

doc: install doc-clean
	QGIS_PREFIX=$(QGIS_PREFIX) python3 -m cli.autodoc

doc-toc:
	QGIS_PREFIX=$(QGIS_PREFIX) python3 -m cli.__init__ toc

doc-build: doc
	python3 -m mkdocs build

doc-serve: doc
	python3 -m mkdocs serve

doc-deploy: doc
	python3 -m mkdocs gh-deploy

doc-clean:
	rm -rf docs/algorithms
	rm -rf site

clean:
	make -C cython clean