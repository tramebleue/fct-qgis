import os
import sys
import yaml

QGIS_PREFIX_PATH = os.environ.get('QGIS_PREFIX_PATH', '/usr/share/qgis')
sys.path.append(os.path.join(QGIS_PREFIX_PATH, 'python/plugins'))
sys.path.append(os.path.join(os.environ['HOME'], '.qgis2/python/plugins'))

from processing import Processing
from processing.gui import AlgorithmExecutor
from processing.tests import AlgorithmsTestBase

from qgis.core import (
    QgsVectorLayer,
    QgsRasterLayer,
    QgsMapLayerRegistry
)

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
        from FluvialToolbox.FluvialToolbox import FluvialToolboxProvider
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

    def check_algorithm(self, name, defs):
        """
        Will run an algorithm definition and check if it generates the expected result
        :param name: The identifier name used in the test output heading
        :param defs: A python dict containing a test algorithm definition
        """
        params = self.load_params(defs['params'])

        alg = Processing.getAlgorithm(defs['algorithm']).getCopy()

        if isinstance(params, list):
            for param in zip(alg.parameters, params):
                param[0].setValue(param[1])
        else:
            for k, p in params.iteritems():
                alg.setParameterValue(k, p)

        for r, p in defs['results'].iteritems():
            alg.setOutputValue(r, self.load_result_param(p))

        # print(alg.getAsCommand())
        self.assertTrue(AlgorithmExecutor.runalg(alg))
        self.check_results(alg.getOutputValuesAsDictionary(), defs['results'])
        self.check_expected_selection(params, defs.get('expected_selection', {}))

    def check_expected_selection(self, params, expected):

        # vectors = { k: v for k, v in params if isinstance(v, QgsVectorLayer) }

        for name, selection in expected.iteritems():

            lyr = params.get(name)
            
            if lyr is None or not isinstance(lyr, QgsVectorLayer):

                raise KeyError('Expected selection does not match any input vectors : %s' % name)

            else:

                selected = set(lyr.selectedFeaturesIds())
                expected_selection = set(selection)
                self.assertEqual(selected, expected_selection)

    def load_layer(self, param):
        """
        Loads a layer which was specified as parameter.
        """
        filepath = self.filepath_from_param(param)

        if param['type'] == 'vector':
        
            lyr = QgsVectorLayer(filepath, param['name'], 'ogr')
        
            if param.has_key('selection'):
                selection = list(param['selection'])
                lyr.setSelectedFeatures(selection)
                # lyr.selectByIds(selection, QgsVectorLayer.SetSelection)
        
        elif param['type'] == 'raster':
            lyr = QgsRasterLayer(filepath, param['name'], 'ogr')

        self.assertTrue(lyr.isValid(), 'Could not load layer "{}"'.format(filepath))
        QgsMapLayerRegistry.instance().addMapLayer(lyr)
        return lyr

    # def assertLayersEqual(self, expected, result, **kwargs):

    #     print expected.name(), expected.dataProvider().crs().authid()
    #     print result.name(), result.dataProvider().crs().authid()
    #     super(TestFluvialToolboxAlgorithms, self).assertLayersEqual(expected, result, **kwargs)

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