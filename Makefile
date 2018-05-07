QGIS_USER_DIR=$(HOME)/.qgis2
PLUGIN_DIR=$(QGIS_USER_DIR)/python/plugins
TARGET=$(PLUGIN_DIR)/fluvialtoolbox
PY_FILES=$(wildcard *.py)
MODEL_FILES=$(wildcard *.model)
MODULES=core main common utils shapelish graph modeler spatial_components
MODULES_PY_FILES=$(foreach module, $(MODULES), $(wildcard $(module)/*.py))
MODULES_MODEL_FILES=$(foreach module, $(MODULES), $(wildcard $(module)/*.model))

install:
	@echo -n Install to $(TARGET) ...
	@mkdir -p $(TARGET)
	@cp metadata.txt $(TARGET)
	@cp $(PY_FILES) $(TARGET)
	# @cp $(MODEL_FILES) $(TARGET)
	@for m in $(MODULES); do mkdir -p $(TARGET)/$$m; done
	@for f in $(MODULES_PY_FILES); do cp $$f $(TARGET)/$$f; done
	@for f in $(MODULES_MODEL_FILES); do cp $$f $(TARGET)/$$f; done
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
