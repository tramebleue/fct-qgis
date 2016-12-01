from PyQt4.QtCore import QDir
from processing.tools.system import tempFolder

def cleanTemporaryFolder():
	tempDir = tempFolder()
	if QDir(tempDir).exists():
		QDir.remove(tempDir)