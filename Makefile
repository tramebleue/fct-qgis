QGIS_USER_DIR=$(HOME)/.qgis2
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/FluvialToolbox
PY_FILES=$(wildcard *.py)
MODULES=core utils 
MODULES_PY_FILES=$(foreach module, $(MODULES), $(wildcard $(module)/*.py))
ICONS=$(wildcard *.png)

default: install

resources.py: resources.qrc
	pyrcc4 -o resources.py resources.qrc

install: resources.py
	@echo -n Install to $(TARGET) ...
	@mkdir -p $(TARGET)
	@cp $(PY_FILES) $(TARGET)
	@for m in $(MODULES); do mkdir -p $(TARGET)/$$m; done
	@for f in $(MODULES_PY_FILES); do cp $$f $(TARGET)/$$f; done
	@cp -R algorithms $(TARGET)
	# @cp -R maptools $(TARGET)
	@cp $(ICONS) $(TARGET)
	@cp *.qrc $(TARGET)
	@cp metadata.txt $(TARGET)
	@echo Ok

uninstall:
	@echo -n Remove directory $(TARGET) ...
	@rm -rf $(TARGET)
	@echo Ok

clean:
	rm -f *.c
	rm -f *.pyc
	rm -f *.so
	rm -rf build
