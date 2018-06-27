from shapely import speedups
from FastFixedDistanceBuffer import FastFixedDistanceBuffer
from FastVariableDistanceBuffer import FastVariableDistanceBuffer

if speedups.available:
    speedups.enable()