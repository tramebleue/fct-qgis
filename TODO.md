* [ ] Dev Strategy
    * [ ] Test Framework for automated tests : split tests YAML into small chunks, one per algorithm
    * [ ] I18n Framework
    * [ ] Write python installer (use `doit`)
    * [ ] Dependencies not available in QGIS3 default installation 
        * [ ] SciPy for morphology operations (eg. BinaryClosing) and better Voronoi Polygons

* [ ] Migration of QGis 2.14 Algorithms to QGis 3.4

    * [x] Tools for Rasters (raster)
        * [x] BinaryClosing
        * [x] DifferentialRasterThreshold (may be replaced by qgis:rastercalculator)
        * [ ] ~~ExtractRasterValueAtPoints~~ (replaced by qgis:rastersampling)
        * [ ] ~~SimpleRasterStatistics~~

    * [ ] Tools for Vectors (vector)
        * [ ] ~~DeduplicateLines~~ (replaced by qgis:deleteduplicategeometries)
        * [ ] InterpolateLine
        * [ ] JoinByNearest
        * [x] LineMidpoints
        * [ ] MeasureDistanceToPointLayer
        * [ ] MergeGeometries
        * [ ] ~~PointOnSurface~~ (replaced by native:pointonsurface)
        * [ ] ~~RandomSamples~~
        * [x] RandomPoissonDiscSamples
        * [x] RegularHexSamples
        * [x] RemoveSmallPolygonalObjects
        * [ ] SafePolygonIntersection
        * [ ] ~~SegmentEndpoints~~ (replaced by qgis:extractspecificvertices)
        * [x] SelectByDistance
        * [x] SelectNearestFeature
        * [ ] ~~SplitLine~~ (replaced by native:explodelines)
        * [ ] ~~SplitLineIntoSegments~~ (replaced by native:explodelines)
        * [x] UniquePoints
        * [ ] ~~UniqueValuesTable~~ (not used)
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
        * [x] LongestPathInDirectedAcyclicGraph (renamed to LongestPathInDirectedGraph)
        * [x] LongestPathInDirectedAcyclicGraphMultiFlow (merged with LongestPathInDirectedGraph)
        * [ ] LongitudinalTransform
        * [ ] MatchNearestLine
        * [ ] MatchNearestLineUpdate
        * [ ] MatchNetworkNodes
        * [ ] MatchNetworkSegments
        * [x] MeasureLinesFromOutlet (renamed to MeasureNetworkFromOutlet)
        * [x] MeasurePointsAlongLine (merged with ProjectPointOnNearestLine)
        * [x] NetworkNodes
        * [x] ProjectPointsAlongLine (renamed to ProjectPointOnNearestLine)
        * [x] ReverseFlowDirection (~~replaced by native:reverselinedirection~~)
        * [x] SelectConnectedComponents
        * [x] SelectDownstreamComponents (merged with SelectConnectedComponents)
        * [ ] SelectFullLengthPaths
        * [ ] SelectGraphCycle
        * [x] SelectMainDrain (renamed to ExportMainDrain)
        * [ ] SelectShortTributaries
        * [x] SelectUpstreamComponents (merged with SelectConnectedComponents)
        * [ ] ~~Sequencing~~ (replaced by BuildDirectedStreamNetwork)
        * [x] StrahlerOrder

    * [ ] Metrics (metrics)
        * [x] DetrendDEM
        * [ ] FilterByMinRank
        * [x] AggregateFeatures
            * [x] Add dissolve result option
            * [ ] Add new segmentation algorithms (Lise Vaudor)
        * [x] ~~LocalFeatureSize~~ (replaced by PolygonWidth)
        * [x] OrthogonalTransects (possible alternative is native:transect)
        * [x] PlanformMetrics
            * [ ] Add summary by DGO
        * [ ] SegmentMeanSlope
        * [ ] SegmentMeanValue
        * [ ] SegmentPlanarSlope
        * [ ] ~~Sinuosity~~
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
        * [x] MedialAxis (replaced by ValleyCenterLine)
        * [x] PolygonSkeleton
        * [ ] ValleyBottom (need to be tested)

    * [ ] ~~Unstable~~ (unstable, must be fixed)
        * [ ] ~~CenterLine~~
        * [ ] ~~LeftRightBox~~
        * [ ] ~~MatchPolygonWithMostImportantLine~~
        * [ ] ~~MatchPolygonWithNearestCentroid~~
        * [ ] ~~SimplifyVisvalingam~~
        * [ ] ~~SplitLineAtNearestPoint~~

* New algorithms
    * [x] TopologicalStreamBurn
    * [x] FlowAccumulation
    * [x] FocalMean/FocalAnalysis (TODO add more aggregation/filter options such as std, median, sum, min, max)
    * [x] SciPyVoronoiPolygons
    * [x] RasterInfo
    * [x] FixLinkOrientation
    * [ ] DirectedStreamNetwork
    * [ ] MeanderingEnvelope
    * [x] ValleyBottom based on dem+flow direction
    * [x] UpstreamChannelLength
    * [x] KnickPoint
    * [x] Vectorize Stream Features
    * [x] SetMCoordFromMeasureField
    * [x] LineStringZSlope
    * [x] TransformCoordinateByExpression
    * [x] LineStringBufferByM
    * [ ] Fill Sinks (Wang & Liu)
    * [ ] Strahler Order (Raster)
    * [ ] Simple Raster Filter (Mean, Median, Max, Min, Std/Var...)
    * [x] ConnectLines
    * [x] Variable Length Transect By Interval
    * [x] Variable Length Transect By Point

* Workflows
    * [ ] Spatial Components
        * [x] Oriented centerline
            * ValleyCenterLine
            * Identify Network Nodes
            * Drape
            * Check/Fix Link orientation
        * [ ] Stream Network
            * Topological stream burn
            * Vectorize streams
            * Orient streams ?
        * [x] Valley bottom
            * RelativeDEM
            * ValleyBottom
    * [x] Disaggregation Processes
        * [x] Polyline disaggregation (=Planform metrics)
        * [x] Segmentation
            * Disaggregate Polygon
            * To complete with disaggregate line
        * [x] Sequencing
            * Identifey network nodes
            * Drape
            * Check/Fix link orientation
    * [ ] Metrics
        * [ ] Contact length
        * [ ] Discontinuities
        * [ ] Elevation and slope
            * Drape
            * LineStringZ Slope
        * [x] Morphometry (=Planform metrics)
        * [ ] Watershed
        * [x] Width (=MeanPolygonByDGO, could be simplyfied by only near feature detection)
    * [x] Statistics
        * [x] Hubert test (=Hubert-Kehagias Aggregation)