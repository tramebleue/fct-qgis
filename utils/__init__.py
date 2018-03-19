from PyQt4.QtCore import QDir
from processing.tools.system import tempFolder

def cleanTemporaryFolder():
    tempDir = tempFolder()
    if QDir(tempDir).exists():
        QDir.remove(tempDir)

class IdGenerator(object):

    def __init__(self):
        self.x = 0

    def __iter__(self):
        return self

    def next(self):
        self.x = self.x + 1
        return self.x