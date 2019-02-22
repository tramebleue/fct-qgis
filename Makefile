QGIS_PREFIX=/usr
QGIS_USER_DIR=$(HOME)/.local/share/QGIS/QGIS3/profiles/default
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/FluvialCorridorToolbox
VERSION=$(shell grep 'version=' fct/metadata.txt | cut -d'=' -f2)
PYTHONPATH=$(QGIS_PREFIX)/share/qgis/python/plugins
PYTHONVERSION=$(shell python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VIRTUALENV=python3
VIRUTALENV_LIBPYTHON=$(VIRTUALENV)/lib/python$(PYTHONVERSION)

default: install

fct/resources.py: fct/resources.qrc fct/icon.png
	pyrcc5 -o fct/resources.py fct/resources.qrc

install: fct/resources.py
	mkdir -p $(TARGET)
	cp -R fct/* $(TARGET)
	@echo
	@echo ----------------------
	@echo Installed to $(TARGET)

environment:
	if [ ! -d $(VIRTUALENV) ]; \
	then \
		virtualenv -p python3 $(VIRTUALENV) ; \
	fi
	rm -f $(VIRUTALENV_LIBPYTHON)/no-global-site-packages.txt
	echo $(PYTHONPATH) > $(VIRUTALENV_LIBPYTHON)/site-packages/qgis-plugins.pth 
	. $(VIRTUALENV)/bin/activate && pip install -e .

extensions:
	make -C cython TARGET=$(TARGET) install

uninstall:
	rm -rf $(TARGET)
	@echo
	@echo ----------------------
	@echo Removed directory: $(TARGET)

doc: install doc-clean
	PYTHONPATH=$(PYTHONPATH) python3 -m fct.cli.autodoc build

doc-toc:
	PYTHONPATH=$(PYTHONPATH) python3 -m fct.cli.autodoc toc

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
	py3clean fct
	rm -f fct/lib/*.so
	rm -rf build
	make -C cython clean

zip: fct/resources.py
	mkdir -p FluvialCorridorToolbox
	cp -R fct/* FluvialCorridorToolbox
	rm -f release/FluvialCorridorToolbox.$(VERSION).zip
	zip -r release/FluvialCorridorToolbox.$(VERSION).zip FluvialCorridorToolbox
	rm -rf FluvialCorridorToolbox
	@echo
	@echo ----------------------
	@echo Zipped to release/FluvialCorridorToolbox.$(VERSION).zip. 
	@echo To release this package, you need to update repo/plugins.xml with the new version.