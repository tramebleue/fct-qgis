from ComputeFrictionCost import ComputeFrictionCost
from DirectedGraphFromUndirected import DirectedGraphFromUndirected
from EdgeWeighting import EdgeWeighting
from FastDeleteExteriorPolygons import FastDeleteExteriorPolygons
from NodesFromEdges import NodesFromEdges
from ShortestDistanceToTargets import ShortestDistanceToTargets
from TrianglesToEdges import TrianglesToEdges
from WeightedDistanceToTargets import WeightedDistanceToTargets

def lateralAlgorithms():

    return [
        ComputeFrictionCost(),
        DirectedGraphFromUndirected(),
        EdgeWeighting(),
        FastDeleteExteriorPolygons(),
        NodesFromEdges(),
        ShortestDistanceToTargets(),
        TrianglesToEdges(),
        WeightedDistanceToTargets()
    ]