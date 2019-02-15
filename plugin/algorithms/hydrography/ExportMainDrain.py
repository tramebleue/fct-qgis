# -*- coding: utf-8 -*-

"""
Export Main Drain

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from collections import defaultdict

from qgis.core import ( # pylint:disable=no-name-in-module
    QgsFeatureRequest,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameters,
    QgsPropertyDefinition
)

from ..metadata import AlgorithmMetadata

class ExportMainDrain(AlgorithmMetadata, QgsProcessingAlgorithm):
    """
    Export Main Drain
    """

    METADATA = AlgorithmMetadata.read(__file__, 'ExportMainDrain')

    INPUT = 'INPUT'
    FROM_NODE_FIELD = 'FROM_NODE_FIELD'
    TO_NODE_FIELD = 'TO_NODE_FIELD'
    COST = 'COST'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, configuration): #pylint: disable=unused-argument,missing-docstring

        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            self.tr('Stream network (polylines)'),
            [QgsProcessing.TypeVectorLine]))

        self.addParameter(QgsProcessingParameterField(
            self.FROM_NODE_FIELD,
            self.tr('From Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEA'))

        self.addParameter(QgsProcessingParameterField(
            self.TO_NODE_FIELD,
            self.tr('To Node Field'),
            parentLayerParameterName=self.INPUT,
            type=QgsProcessingParameterField.Numeric,
            defaultValue='NODEB'))

        param_cost = QgsProcessingParameterNumber(
            self.COST,
            self.tr('Traversal Cost'),
            defaultValue=0.0)
        param_cost.setIsDynamic(True)
        param_cost.setDynamicLayerParameterName(self.COST)
        param_cost.setDynamicPropertyDefinition(
            QgsPropertyDefinition(
                self.COST,
                self.tr('Traversal Cost'),
                QgsPropertyDefinition.Double))
        self.addParameter(param_cost)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            self.tr('Main Drain'),
            QgsProcessing.TypeVectorLine))


    def processAlgorithm(self, parameters, context, feedback): #pylint: disable=unused-argument,missing-docstring

        layer = self.parameterAsSource(parameters, self.INPUT, context)
        from_node_field = self.parameterAsString(parameters, self.FROM_NODE_FIELD, context)
        to_node_field = self.parameterAsString(parameters, self.TO_NODE_FIELD, context)
        cost_default = self.parameterAsDouble(parameters, self.COST, context)
        dynamic = QgsProcessingParameters.isDynamic(parameters, self.COST)
        cost_property = parameters[self.COST] if dynamic else None

        (sink, dest_id) = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs())

        feedback.setProgressText(self.tr('Build Upward Index ...'))

        # forwardtracks = { nb: list(segment, na, cost) }
        forwardtracks = defaultdict(list)
        total = 100.0 / layer.featureCount() if layer.featureCount() else 0
        anodes = set()

        for current, feature in enumerate(layer.getFeatures()):

            # toi = feature.attribute('TOI')
            # if toi == 0:
            #     continue

            context.expressionContext().setFeature(feature)

            a = feature.attribute(from_node_field)
            b = feature.attribute(to_node_field)

            if dynamic:
                value, ok = cost_property.valueAsDouble(context.expressionContext(), cost_default)
                cost = value if ok else cost_default
            else:
                cost = cost_default

            forwardtracks[b].append((feature.id(), a, cost))
            anodes.add(a)

            feedback.setProgress(int(current * total))

        feedback.setProgressText(self.tr('Walk up from Outlets to Sources ...'))

        # backtracks = { ba: segment, nb, cost }
        backtracks = dict()
        sources = list()
        stack = list(set(forwardtracks.keys()) - anodes)
        del anodes

        while stack:

            if feedback.isCanceled():
                break

            nb = stack.pop()

            if nb in backtracks:
                sb, nbb, cost = backtracks[nb]
            else:
                cost = 0.0

            for segment, na, step_cost in forwardtracks[nb]:

                new_cost = cost + step_cost

                if na in backtracks:

                    sa, nba, costa = backtracks[na]
                    if new_cost < costa:
                        backtracks[na] = (segment, nb, new_cost)

                else:

                    backtracks[na] = (segment, nb, new_cost)

                    if na in forwardtracks:
                        stack.append(na)
                    else:
                        sources.append(na)

        feedback.setProgressText(self.tr('Select main drain ...'))

        current = 0
        segments = set()

        for source in sources:

            if feedback.isCanceled():
                break

            na = source

            while na in backtracks:

                if feedback.isCanceled():
                    break

                segment, nb, cost = backtracks[na]

                if segment not in segments:

                    # feature = network.getFeatures(QgsFeatureRequest(segment)).next()
                    segments.add(segment)

                    current = current + 1
                    feedback.setProgress(int(current * total))

                na = nb

        feedback.setProgressText(self.tr('Export selected features ...'))

        request = QgsFeatureRequest().setFilterFids([fid for fid in segments])
        total = 100.0 / len(segments) if segments else 0

        for current, feature in enumerate(layer.getFeatures(request)):

            sink.addFeature(feature)
            feedback.setProgress(int(current*total))

        return {
            self.OUTPUT: dest_id
        }
