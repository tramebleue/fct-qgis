QGIS_USER_DIR=$(HOME)/.local/share/QGIS/QGIS3/profiles/default
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/FluvialCorridorToolbox
PY_FILES=$(wildcard *.py)
MODULES=core utils 
MODULES_PY_FILES=$(foreach module, $(MODULES), $(wildcard $(module)/*.py))
ICONS=$(wildcard *.png)

default: install

resources.py: resources.qrc
	pyrcc5 -o resources.py resources.qrc

install: resources.py
	@echo Install to $(TARGET) ...
	mkdir -p $(TARGET)
	@cp $(PY_FILES) $(TARGET)
	@for m in $(MODULES); do mkdir -p $(TARGET)/$$m; done
	@for f in $(MODULES_PY_FILES); do cp $$f $(TARGET)/$$f; done
	cp -R algorithms $(TARGET)
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
