* [ ] Test Framework for automated tests

* [ ] Dependencies not available in QGIS3 default installation 
    * [ ] SciPy for BinaryClosing

* [ ] Algorithms update for QGIS 3.4

    * Tools for Rasters (raster)
        * [x] BinaryClosing
        * [x] DifferentialRasterThreshold (may be replaced by qgis:rastercalculator)
        * [ ] ~~ExtractRasterValueAtPoints~~ (replaced by qgis:rastersampling)
        * [ ] SimpleRasterStatistics

    * Tools for Vectors (vector)
        * [ ] DeduplicateLines
        * [ ] InterpolateLine
        * [ ] JoinByNearest
        * [ ] LineMidpoints
        * [ ] MeasureDistanceToPointLayer
        * [ ] MergeGeometries
        * [ ] ~~PointOnSurface~~ (replaced by native:pointonsurface)
        * [ ] RandomPoints
        * [x] RandomPoissonDiscSampling
        * [x] RegularHexPoints
        * [x] RemoveSmallPolygonalObjects
        * [ ] SafePolygonIntersection
        * [ ] SegmentEndpoints
        * [ ] SelectByDistance
        * [ ] SelectNearestFeature
        * [ ] SplitLine
        * [ ] SplitLineIntoSegments
        * [ ] UniquePoints
        * [ ] UniqueValuesTable
        * [ ] UpdateFieldByExpression
        * [ ] UpdateFieldByExpressionInPlace

    * Hydrography (hydrography)
        * [x] AggregateLineSegments
        * [x] AggregateLineSegmentsByCat (merged with AggregateLineSegments)
        * [ ] DensifyNetworkNodes
        * [ ] IdentifyNetworkNodes
        * [ ] InverseLongitudinalTransform
        * [x] LengthOrder
        * [ ] LocatePolygonAlongLine
        * [ ] LongestPathInDirectedAcyclicGraph
        * [ ] LongestPathInDirectedAcyclicGraphMultiFlow
        * [ ] LongitudinalTransform
        * [ ] MatchNearestLine
        * [ ] MatchNearestLineUpdate
        * [ ] MatchNetworkNodes
        * [ ] MatchNetworkSegments
        * [ ] MeasureLinesFromOutlet
        * [ ] MeasurePointsAlongLine
        * [x] NetworkNodes
        * [ ] ProjectPointsAlongLine
        * [ ] ~~ReverseFlowDirection~~ (replaced by native:reverselinedirection ?)
        * [ ] SelectConnectedComponents
        * [ ] SelectDownstreamComponents
        * [ ] SelectFullLengthPaths
        * [ ] SelectGraphCycle
        * [ ] SelectMainDrain
        * [ ] SelectShortTributaries
        * [x] SelectUpstreamComponents
        * [ ] Sequencing
        * [x] StrahlerOrder

    * Metrics (metrics)
        * [ ] DetrendDEM
        * [ ] FilterByMinRank
        * [ ] LocalFeatureSize
        * [ ] ~~OrthogonalTransects~~ (replaced by native:transect)
        * [ ] PlanformMetrics
        * [ ] SegmentMeanSlope
        * [ ] SegmentMeanValue
        * [ ] SegmentPlanarSlope
        * [ ] Sinuosity
        * [ ] Sum
        * [ ] WeightedMean

    * Lateral (lateral)
        * [ ] FastDeleteExteriorPolygons
        * [ ] EdgeWeighting
        * [ ] ShortestDistanceToTargets
        * [ ] WeightedDistanceToTargets
        * [ ] ComputeFrictionCost
        * [ ] TrianglesToEdges
        * [ ] NodesFromEdges
        * [ ] DirectedGraphFromUndirected

    * Spatial Components (spatial_components)
        * [ ] DisaggregatePolygon
        * [ ] LeftRightDGO
        * [ ] MedialAxis
        * [ ] PolygonSkeleton
        * [ ] ValleyBottom

    * Unstable (unstable, must be fixed)
        * [ ] CenterLine
        * [ ] LeftRightBox
        * [ ] MatchPolygonWithMostImportantLine
        * [ ] MatchPolygonWithNearestCentroid
        * [ ] SimplifyVisvalingam
        * [ ] SplitLineAtNearestPoint

