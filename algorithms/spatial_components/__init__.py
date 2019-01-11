from .DetrendDEM import DetrendDEM
from .ValleyBottom import ValleyBottom
from .DisaggregatePolygon import DisaggregatePolygon

def spatial_componentsAlgorithms():

    return [
    	DetrendDEM(),
    	ValleyBottom(),
        DisaggregatePolygon()
    ]

    # return [
    #     DisaggregatePolygon(),
    #     LeftRightDGO(),
    #     MedialAxis(),
    #     PolygonSkeleton(),
    #     ValleyBottom()
    # ]
