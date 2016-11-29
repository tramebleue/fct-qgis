Valley Bottom
-------------

Inputs :

- ZOI (polygon)
- DEM (raster)
- Stream network (polyline)

Output :

- ValleyBottom (polygon)

Parameters :

- SimplifyParameters = 20
- SplitDistance = 50 m
- SmallBufferDistance = 50 m
- LargeBufferDistance = 1000 m
- MinRelativeDEMValue = -9 m
- MaxRelativeDEMValue = 10 m
- MinPolygonArea = 50 ha
- MaxHoleArea = 10 ha
- SmoothingParameters
- TemporaryDirectory

Steps :

- SplitNetwork <- Split(Simplify(StreamNetwork && ZOI, SimplifyParameters), SplitDistance)
- SmallBuffer <- Buffer(SplitNetwork, SmallBufferDistance)
- LargeBuffer <- Buffer(SplitNetwork, LargeBufferDistance)
- ProcessDEM <- DEM && LargeBuffer
- ThiessenPolygons <- Voronoi(PolylineToPoints(SplitNetwork), Box(LargeBuffer))
- ClippedThiessenPolygons <- ThiessenPolygons && LargeBuffer
- ReferenceDEM <- Rasterize(Mean(ProcessDEM && SmallBuffer, ClippedThiessenPolygons))
- RelativeDEM <- ProcessDEM - ReferenceDEM
- ValleyBottomMask <- RelativeDEM >= MinRelativeDEMValue And RelativeDEM <= MaxRelativeDEMValue
- UncleanedValleyBottom <- Polygonize(Sieve(ValleyBottomMask, 20)) WHERE Value = 1 AND AREA >= MinPolygonArea

Cleaning Steps :

- ValleyBottom <- EliminateHoles(UncleanedValleyBottom, AREA < 10 ha)
- ValleyBottom <- Smooth(Aggregate(ValleyBottom), SmoothingParameters)
- CleanTemporaryData

Routines :

- GeometryClip(geometry && polygon) =
	ogr.Geometry.Intersection()
	processing.alg.qgis.Clip(input, overlay)
- Simplify =
	ogr.Geometry.SimplifyPreserveTopology() (DouglasPeuker)
	processing.alg.qgis.SimplifyGeometries(tolerance)
- Split =
	fluvialtoolbox.SplitLineString()
- RasterClip(raster && polygon) =
	gdal.Warp()
	processing.alg.gdal.ClipByMask()
- Box = ogr.Geometry.Boundary()
- PolylineToPoints =
	ogr.Geometry.GetPoints()
	processing.alg.qgis.ExtractNodes()
- Voronoi =
	processing.alg.qgis.VoronoiPolygons
- Buffer = 
	ogr.Geometry.Buffer()
	processing.alg.qgis.Buffer()
- Mean =
	cf. ZonalStatistics : gdal/ogr/numpy routine
	processing.alg.qgis.ZonalStatistics()
- MapAlgebra =
	numpy routine
	qgis.analysis.QgsRasterCalculator()
- Rasterize =
	gdal.Rasterize()
	processing.alg.gdal.rasterize()
- Polygonize =
	gdal.Polygonize()
	processing.alg.gdal.polygonize()
- EliminateHoles
	processing.alg.qgis.DeleteHoles(input)
- Aggregate
	processing.alg.qgis.Dissolve(input)
- Smooth
	processing.alg.qgis.Smooth(input)

processing.runalg(name, consoleName, parameters)
code indépendant de QGis ?
implémentation pour PostGIS ?