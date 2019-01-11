* [ ] Dev Strategy
    * [ ] Test Framework for automated tests : split tests YAML into small chunks, one per algorithm
    * [ ] I18n Framework
    * [ ] Write python installer
    * [ ] Dependencies not available in QGIS3 default installation 
        * [ ] SciPy for BinaryClosing

* [ ] Migration of QGis 2.14 Algorithms to QGis 3.4

    * [x] Tools for Rasters (raster)
        * [x] BinaryClosing
        * [x] DifferentialRasterThreshold (may be replaced by qgis:rastercalculator)
        * [ ] ~~ExtractRasterValueAtPoints~~ (replaced by qgis:rastersampling)
        * [ ] ~~SimpleRasterStatistics~~

    * [ ] Tools for Vectors (vector)
        * [ ] DeduplicateLines
        * [ ] InterpolateLine
        * [ ] JoinByNearest
        * [x] LineMidpoints
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

    * [ ] Hydrography (hydrography)
        * [x] AggregateLineSegments
        * [x] AggregateLineSegmentsByCat (merged with AggregateLineSegments)
        * [ ] DensifyNetworkNodes
        * [x] IdentifyNetworkNodes
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
        * [x] MeasureLinesFromOutlet (renamed to MeasureNetworkFromOutlet)
        * [ ] MeasurePointsAlongLine
        * [x] NetworkNodes
        * [ ] ProjectPointsAlongLine
        * [ ] ~~ReverseFlowDirection~~ (replaced by native:reverselinedirection ?)
        * [x] SelectConnectedComponents
        * [x] SelectDownstreamComponents (merged with SelectConnectedComponents)
        * [ ] SelectFullLengthPaths
        * [ ] SelectGraphCycle
        * [ ] SelectMainDrain
        * [ ] SelectShortTributaries
        * [x] SelectUpstreamComponents (merged with SelectConnectedComponents)
        * [ ] ~~Sequencing~~ (replaced by BuildDirectedStreamNetwork)
        * [x] StrahlerOrder

    * [ ] Metrics (metrics)
        * [x] DetrendDEM
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

    * [ ] Lateral (lateral)
        * [ ] FastDeleteExteriorPolygons
        * [ ] EdgeWeighting
        * [ ] ShortestDistanceToTargets
        * [ ] WeightedDistanceToTargets
        * [ ] ComputeFrictionCost
        * [ ] TrianglesToEdges
        * [ ] NodesFromEdges
        * [ ] DirectedGraphFromUndirected

    * Spatial Components (spatial_components)
        * [x] DisaggregatePolygon
        * [ ] LeftRightDGO
        * [ ] MedialAxis
        * [ ] PolygonSkeleton
        * [ ] ValleyBottom

    * [ ] Unstable (unstable, must be fixed)
        * [ ] CenterLine
        * [ ] ~~LeftRightBox~~
        * [ ] MatchPolygonWithMostImportantLine
        * [ ] MatchPolygonWithNearestCentroid
        * [ ] ~~SimplifyVisvalingam~~
        * [ ] ~~SplitLineAtNearestPoint~~

* New algorithms
    * [x] TopologicalStreamBurn
    * [x] FlowAccumulation
    * [x] FocalMean/FocalAnalysis (TODO add more aggregation/filter options such as std, median, sum, min, max)
    * [x] SciPyVoronoiPolygons
    * [x] RasterInfo
    * [ ] FixLinkOrientation
    * [ ] BuildDirectedStreamNetwork
    * [ ] MeanderingEnvelope
    * [ ] ValleyBottom based on dem+flow direction
    * [x] UpstreamChannelLength
