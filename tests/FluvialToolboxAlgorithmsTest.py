import os
import sys
import yaml

QGIS_PREFIX_PATH = os.environ.get('QGIS_PREFIX_PATH', '/usr/share/qgis')
sys.path.append(os.path.join(QGIS_PREFIX_PATH, 'python/plugins'))
sys.path.append(os.path.join(os.environ['HOME'], '.qgis2/python/plugins'))

from processing.tests import AlgorithmsTestBase

import nose2
import shutil

from qgis.testing import (
    start_app,
    unittest
)

def processingTestDataPath():
    return os.path.join(os.path.dirname(__file__), 'testdata')

class TestFluvialToolboxAlgorithms(unittest.TestCase, AlgorithmsTestBase.AlgorithmsTest):

    @classmethod
    def setUpClass(cls):
        start_app()
        from processing.core.Processing import Processing
        from fluvialtoolbox.FluvialToolbox import FluvialToolboxProvider
        Processing.initialize()
        provider = FluvialToolboxProvider()
        Processing.addProvider(provider)
        cls.cleanup_paths = []

    @classmethod
    def tearDownClass(cls):
        for path in cls.cleanup_paths:
            shutil.rmtree(path)

    def test_algorithms(self):
        """
        This is the main test function. All others will be executed based on the definitions in testdata/tests.yaml
        """
        # ver = processing.version()
        # print("Processing {}.{}.{}".format(ver / 10000, ver / 100 % 100, ver % 100))
        with open(os.path.join('testdata', self.test_definition_file()), 'r') as stream:
            algorithm_tests = yaml.load(stream)

        for algtest in algorithm_tests['tests']:
            yield self.check_algorithm, algtest['name'], algtest

    def filepath_from_param(self, param):
        """
        Creates a filepath from a param
        """
        prefix = processingTestDataPath()
        if 'location' in param and param['location'] == 'qgs':
            prefix = unitTestDataPath()
        elif 'location' in param:
            prefix = param['location']

        return os.path.join(prefix, param['name'])

    def test_definition_file(self):
        return 'tests.yaml'


if __name__ == '__main__':
    nose2.main()