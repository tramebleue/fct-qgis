from .DetrendDEM import DetrendDEM
from .ValleyBottom import ValleyBottom

def spatial_componentsAlgorithms():

    return [
    	DetrendDEM(),
    	ValleyBottom()
    ]

    # return [
    #     DisaggregatePolygon(),
    #     LeftRightDGO(),
    #     MedialAxis(),
    #     PolygonSkeleton(),
    #     ValleyBottom()
    # ]
