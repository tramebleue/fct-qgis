PLUGIN_DIR=$(HOME)/.qgis2/python/plugins
TARGET=$(PLUGIN_DIR)/fluvialtoolbox

install:
	mkdir -p $(TARGET)
	cp *.py metadata.txt $(TARGET)

uninstall:
	rm -rf $(TARGET)

clean:
	rm -f *.c
	rm -f *.pyc
	rm -f *.so
	rm -rf build
