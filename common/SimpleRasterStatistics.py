# -*- coding: utf-8 -*-

"""
***************************************************************************
    ZonalStatistics.py
    ---------------------
    Date                 : August 2013
    Copyright            : (C) 2013 by Alexander Bruy
    Email                : alexander dot bruy at gmail dot com
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

__author__ = 'Alexander Bruy'
__date__ = 'August 2013'
__copyright__ = '(C) 2013, Alexander Bruy'

# This will get replaced with a git SHA1 when you do a git archive

__revision__ = '$Format:%H$'

import numpy

try:
    from scipy.stats.mstats import mode
    hasSciPy = True
except:
    hasSciPy = False

from osgeo import gdal, ogr, osr
from qgis.core import QgsRectangle, QgsGeometry, QgsFeature, QgsFields, QgsField
from PyQt4.QtCore import QVariant

from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import ParameterVector
from processing.core.parameters import ParameterRaster
from processing.core.parameters import ParameterString
from processing.core.parameters import ParameterNumber
from processing.core.parameters import ParameterBoolean
from processing.core.parameters import ParameterSelection
from processing.core.parameters import ParameterTableField
from processing.core.outputs import OutputVector
from processing.tools.raster import mapToPixel
from processing.tools import dataobjects, vector


class SimpleRasterStatistics(GeoAlgorithm):

    INPUT_RASTER = 'INPUT_RASTER'
    RASTER_BAND = 'RASTER_BAND'
    INPUT_VECTOR = 'INPUT_VECTOR'
    PRIMARY_KEY = 'PRIMARY_KEY'
    COLUMN_PREFIX = 'COLUMN_PREFIX'
    STATISTICS  = 'STATISTICS'
    OUTPUT_LAYER = 'OUTPUT_LAYER'

    def defineCharacteristics(self):

        self.name, self.i18n_name = self.trAlgorithm('Simple Raster Statistics')
        self.group, self.i18n_group = self.trAlgorithm('Common Routines')

        self.addParameter(ParameterRaster(self.INPUT_RASTER,
                                          self.tr('Raster layer')))
        self.addParameter(ParameterNumber(self.RASTER_BAND,
                                          self.tr('Raster band'), 1, 999, 1))
        self.addParameter(ParameterVector(self.INPUT_VECTOR,
                                          self.tr('Vector layer containing zones'),
                                          [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterTableField(self.PRIMARY_KEY,
                                              self.tr('Primary Key'),
                                              parent=self.INPUT_VECTOR))
        self.addParameter(ParameterSelection(self.STATISTICS,
                                             self.tr('Statistics'),
                                             options=[
                                                self.tr('[0] mean'),
                                                self.tr('[1] min/max'),
                                                self.tr('[2] std/count'),
                                                self.tr('[3] median'),
                                                self.tr('[4] full')
                                             ]))
        self.addParameter(ParameterString(self.COLUMN_PREFIX,
                                          self.tr('Output column prefix'), '_'))
        self.addOutput(OutputVector(self.OUTPUT_LAYER, self.tr('Simple Raster statistics')))

    def processAlgorithm(self, progress):
        """ Based on code by Matthew Perry
            https://gist.github.com/perrygeo/5667173
        """

        layer = dataobjects.getObjectFromUri(self.getParameterValue(self.INPUT_VECTOR))

        rasterPath = unicode(self.getParameterValue(self.INPUT_RASTER))
        bandNumber = self.getParameterValue(self.RASTER_BAND)
        columnPrefix = self.getParameterValue(self.COLUMN_PREFIX)
        primaryKey = self.getParameterValue(self.PRIMARY_KEY)
        statistics = self.getParameterValue(self.STATISTICS)

        rasterDS = gdal.Open(rasterPath, gdal.GA_ReadOnly)
        geoTransform = rasterDS.GetGeoTransform()
        rasterBand = rasterDS.GetRasterBand(bandNumber)
        noData = rasterBand.GetNoDataValue()

        cellXSize = abs(geoTransform[1])
        cellYSize = abs(geoTransform[5])
        rasterXSize = rasterDS.RasterXSize
        rasterYSize = rasterDS.RasterYSize

        rasterBBox = QgsRectangle(geoTransform[0], geoTransform[3] - cellYSize
                                  * rasterYSize, geoTransform[0] + cellXSize
                                  * rasterXSize, geoTransform[3])

        rasterGeom = QgsGeometry.fromRect(rasterBBox)

        crs = osr.SpatialReference()
        crs.ImportFromProj4(str(layer.crs().toProj4()))

        memVectorDriver = ogr.GetDriverByName('Memory')
        memRasterDriver = gdal.GetDriverByName('MEM')

        fields = QgsFields()
        idxPk = 0
        pkField = layer.pendingFields().field(primaryKey)
        fields.append(pkField)

        def createNumericField(name, fields, length=21, prec=6):
            idx = len(fields)
            field = QgsField(name, QVariant.Double, len=length, prec=prec)
            fields.append(field)
            return idx

        if statistics >= 0:
            idxMean = createNumericField(columnPrefix + 'mean', fields)

        if statistics >= 1:
            idxMin = createNumericField(columnPrefix + 'min', fields)
            idxMax = createNumericField(columnPrefix + 'max', fields)

        if statistics >= 2:
            idxStd = createNumericField(columnPrefix + 'std', fields)
            idxCount = createNumericField(columnPrefix + 'count', fields)

        if statistics >= 3:
            idxMedian = createNumericField(columnPrefix + 'median', fields)

        if statistics >= 4:
            idxSum = createNumericField(columnPrefix + 'sum', fields)
            idxUnique = createNumericField(columnPrefix + 'unique', fields)
            idxRange = createNumericField(columnPrefix + 'range', fields)
            idxVar = createNumericField(columnPrefix + 'var', fields)

            if hasSciPy:
                idxMode = createNumericField(columnPrefix + 'mode', fields)

        writer = self.getOutputFromName(self.OUTPUT_LAYER).getVectorWriter(
            fields.toList(), layer.wkbType(), layer.crs())

        outFeat = QgsFeature()

        outFeat.initAttributes(len(fields))
        outFeat.setFields(fields)

        features = vector.features(layer)
        total = 100.0 / len(features)
        for current, f in enumerate(features):
            geom = f.geometry()

            intersectedGeom = rasterGeom.intersection(geom)
            ogrGeom = ogr.CreateGeometryFromWkt(intersectedGeom.exportToWkt())

            bbox = intersectedGeom.boundingBox()

            xMin = bbox.xMinimum()
            xMax = bbox.xMaximum()
            yMin = bbox.yMinimum()
            yMax = bbox.yMaximum()

            (startColumn, startRow) = mapToPixel(xMin, yMax, geoTransform)
            (endColumn, endRow) = mapToPixel(xMax, yMin, geoTransform)

            width = endColumn - startColumn
            height = endRow - startRow

            if width == 0 or height == 0:
                continue

            srcOffset = (startColumn, startRow, width, height)
            srcArray = rasterBand.ReadAsArray(*srcOffset)
            srcArray = srcArray * rasterBand.GetScale() + rasterBand.GetOffset()

            newGeoTransform = (
                geoTransform[0] + srcOffset[0] * geoTransform[1],
                geoTransform[1],
                0.0,
                geoTransform[3] + srcOffset[1] * geoTransform[5],
                0.0,
                geoTransform[5],
            )

            # Create a temporary vector layer in memory
            memVDS = memVectorDriver.CreateDataSource('out')
            memLayer = memVDS.CreateLayer('poly', crs, ogr.wkbPolygon)

            ft = ogr.Feature(memLayer.GetLayerDefn())
            ft.SetGeometry(ogrGeom)
            memLayer.CreateFeature(ft)
            ft.Destroy()

            # Rasterize it
            rasterizedDS = memRasterDriver.Create('', srcOffset[2],
                                                  srcOffset[3], 1, gdal.GDT_Byte)
            rasterizedDS.SetGeoTransform(newGeoTransform)
            gdal.RasterizeLayer(rasterizedDS, [1], memLayer, burn_values=[1])
            rasterizedArray = rasterizedDS.ReadAsArray()

            srcArray = numpy.nan_to_num(srcArray)
            masked = numpy.ma.MaskedArray(srcArray,
                                          mask=numpy.logical_or(srcArray == noData,
                                                                numpy.logical_not(rasterizedArray)))

            outFeat.setGeometry(geom)
            outFeat.setAttribute(idxPk, f.attribute(primaryKey))

            if statistics >= 0:
                v = float(masked.mean())
                outFeat.setAttribute(idxMean, None if numpy.isnan(v) else v)

            if statistics >= 1:
                v = float(masked.min())
                outFeat.setAttribute(idxMin, None if numpy.isnan(v) else v)
                v = float(masked.max())
                outFeat.setAttribute(idxMax, None if numpy.isnan(v) else v)

            if statistics >= 2:
                v = float(masked.std())
                outFeat.setAttribute(idxStd, None if numpy.isnan(v) else v)
                outFeat.setAttribute(idxCount, int(masked.count()))

            if statistics >= 3:
                v = float(numpy.ma.median(masked))
                outFeat.setAttribute(idxMedian, None if numpy.isnan(v) else v)
                
            if statistics >= 4:
                v = float(masked.sum())
                outFeat.setAttribute(idxSum, None if numpy.isnan(v) else v)
                outFeat.setAttribute(idxUnique, numpy.unique(masked.compressed()).size)
                v = float(masked.max()) - float(masked.min())
                outFeat.setAttribute(idxRange, None if numpy.isnan(v) else v)
                v = float(masked.var())
                outFeat.setAttribute(idxVar, None if numpy.isnan(v) else v)
                if hasSciPy:
                    outFeat.setAttribute(idxMode, float(mode(masked, axis=None)[0][0]))

            writer.addFeature(outFeat)

            memVDS = None
            rasterizedDS = None

            progress.setPercentage(int(current * total))

        rasterDS = None

        del writer
