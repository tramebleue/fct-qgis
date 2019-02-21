QGIS_PREFIX=/usr
QGIS_USER_DIR=$(HOME)/.local/share/QGIS/QGIS3/profiles/default
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/FluvialCorridorToolbox
VERSION=$(shell grep 'version=' plugin/metadata.txt | cut -d'=' -f2)

default: install

plugin/resources.py: plugin/resources.qrc plugin/icon.png
	pyrcc5 -o plugin/resources.py plugin/resources.qrc

install: plugin/resources.py
	mkdir -p $(TARGET)
	cp -R plugin/* $(TARGET)
	@echo
	@echo ----------------------
	@echo Installed to $(TARGET)

extensions:
	make -C cython TARGET=$(TARGET) install

uninstall:
	rm -rf $(TARGET)
	@echo
	@echo ----------------------
	@echo Removed directory: $(TARGET)

doc: install doc-clean
	QGIS_PREFIX=$(QGIS_PREFIX) PLUGIN_DIR=$(PLUGIN_DIR) python3 -m cli.__init__ autodoc

doc-toc:
	QGIS_PREFIX=$(QGIS_PREFIX) PLUGIN_DIR=$(PLUGIN_DIR) python3 -m cli.__init__ toc

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

zip: plugin/resources.py
	mkdir -p FluvialCorridorToolbox
	cp -R plugin/* FluvialCorridorToolbox
	rm -f release/FluvialCorridorToolbox.$(VERSION).zip
	zip -r release/FluvialCorridorToolbox.$(VERSION).zip FluvialCorridorToolbox
	rm -rf FluvialCorridorToolbox
	@echo
	@echo ----------------------
	@echo Zipped to release/FluvialCorridorToolbox.$(VERSION).zip. 
	@echo To release this package, you need to update repo/plugins.xml with the new version.