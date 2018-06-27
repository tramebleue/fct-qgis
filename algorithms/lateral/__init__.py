from ComputeFrictionCost import ComputeFrictionCost
from DirectedGraphFromUndirected import DirectedGraphFromUndirected
from FastDeleteExteriorPolygons import FastDeleteExteriorPolygons
from NodesFromEdges import NodesFromEdges
from ShortestDistanceToTargets import ShortestDistanceToTargets
from TrianglesToEdges import TrianglesToEdges

def lateralAlgorithms():

    return [
        ComputeFrictionCost(),
        DirectedGraphFromUndirected(),
        FastDeleteExteriorPolygons(),
        NodesFromEdges(),
        ShortestDistanceToTargets(),
        TrianglesToEdges()
    ]