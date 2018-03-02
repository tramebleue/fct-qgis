from processing.modeler.ModelerAlgorithm import ModelerAlgorithm
from utils import model_filename

def LocalFeatureSize():

    return ModelerAlgorithm.fromJsonFile(model_filename(__file__))