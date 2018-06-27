from processing.modeler.ModelerAlgorithm import ModelerAlgorithm
from ...core.utils import model_filename

def MedialAxis():

    return ModelerAlgorithm.fromJsonFile(model_filename(__file__))