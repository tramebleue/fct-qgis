# Migration des algorithmes de la toolbox vers QGis 3.4

1. Mise à jour de le section `import`
2. Choix de la classe d'algorithme à hériter
3. Mise à jour de la définition de l'algorithme
4. Modification de l'implémentation
5. Substitution des classes modifiées dans l'API QGis 3
6. Ajouter des tests unitaires

## Documentation utile

* [Nouvelle API Processing](https://qgis.org/pyqgis/3.4/core/Processing)

## Mise à jour de la section `import`

Supprimer toute la section `import`
et la remplacer par le template suivante, en éliminant les imports inutiles :

```
from qgis.PyQt.QtCore import (
    QVariant
)

from qgis.core import (
    QgsApplication,
    QgsGeometry,
    QgsFeatureSink,
    QgsFeatureRequest,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsPointXY,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingFeatureBasedAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterDistance,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterField,
    QgsProcessingParameterVectorLayer,
    QgsSpatialIndex,
    QgsWkbTypes
)

from ..metadata import AlgorithmMetadata
```

## Choix de la classe d'algorithme à hériter

* si l'algorithme applique une transformation entité par entité, indépendamment les unes des autres,
  hériter de `QgsProcessingFeatureBasedAlgorithm`

* si l'algorithme est implémenté sous la forme d'un modèle,
  utiliser la classe `QgsProcessingModelAlgorithm` (voir l'exemple ...)

* cas général : hériter de `QgsProcessingAlgorithm`

## Mise à jour de la définition de l'algorithme

La méthode `defineCharacteristics(self)` est remplacée par plusieurs méthodes
qui définissent le nom, le groupe, les paramètres en entrée et en sortie de l'algorithme :

```
    def name(self):
        return 'algname'

    def displayName(self):
        return self.tr('Algorithm Name')

    def groupId(self):
        return 'grid'

    def groupName(self):
        return self.tr('Group Name')

    # optional
    def icon(self):
       return QgsApplication.getThemeIcon('path/to/svg')
    
    def svgIconPath(self):
        return return QgsApplication.iconPath('path/to/svg')

    def tags(self):
        return 'tag1,tag2'.split(',').map(self.tr)

    def flags(self):
        return [ QgsProcessingAlgorithm.FlagCanCancel, QgsProcessingAlgorithm.FlagSupportsBatch ]

    def helpString(self):
        return 'help string'

    def helpUrl(self):
        return 'url'

    def shortDescription(self):
        return 'description'

    def shortHelpString(self):
        return 'short help string'
```

Lorsqu'on hérite de `QgsProcessingAlgorithm`, les paramètres d'entrée et sortie sont définies dans la méthode `initAlgorithm()` :

```
    def initAlgorithm(self, configuration):
        # self.addParameter(...)
        # self.addOutput(...)
```

QGis 2.14                            | QGis 3.4
-------------------------------------|-------------------------------
ParameterVector.VECTOR_TYPE_POINT    | QgsProcessing.TypeVectorPoint
ParameterVector.VECTOR_TYPE_LINE     | QgsProcessing.TypeVectorLine
ParameterVector.VECTOR_TYPE_POLYGON  | QgsProcessing.TypeVectorPolygon
ParameterVector.VECTOR_TYPE_ANY      | QgsProcessing.TypeVectorAnyGeometry
ParameterTableField.DATA_TYPE_NUMBER | QgsProcessingParameterField.Numeric

Lorsqu'on hérite de `QgsProcessingFeatureBasedAlgorithm`,
on peut aussi utiliser les méthodes suivantes pour définir les entrées et les sorties :

```
    def initParameters(self):
        # define any extra parameters
        # self.addParameter(...)

    def inputLayerTypes(self):
        return [ QgsProcessing.TypeVectorPolygon ]

    def outputName(self):
        return self.tr('Output Name')

    def outputLayerType(self):
        return QgsProcessing.TypeVectorPoint

    def outputWkbType(self, inputWkbType):
        return QgsWkbTypes.Point

    def outputFields(self, inputFields):
        return ...

```


## Modification de l'implémentation

Lorsqu'on hérite de `QgsProcessingAlgorithm`, implémenter les méthodes :

* `prepareAlgorithm(self, parameters, context, feedback)`, optionnel, pour récupérer la valeur des paramètres notamment
* `processAlgorithm(self, parameters, context, feedback)`
* `postprocessAlgorithm(self, context, feedback)`, optionnel

La boucle principale de `processAlgorithm()` doit vérifier `feedback.isCanceled()`
et sortir de la boucle si nécessaire.

Lorsqu'on hérite de `QgsProcessingFeatureBasedAlgorithm`, implémenter les méthodes :

* `prepareAlgorithm(self, parameters, context, feedback)`, pour récupérer la valeur des paramètres notamment
* `processFeature(self, feature, context, feedback`, implémente l'opération à effectuer pour chaque entité en entrée
* `postprocessAlgorithm(self, context, feedback)`, optionnel


## Substitution des classes modifiées dans l'API QGis 3.x

QGis 2.14                       | QGis 3.4
--------------------------------|-------------------------------
`QgsPoint`                      | `QgsPointXY`
`ParameterNumber`               | `QgsProcessingParameterNumber` or `QgsProcessingParameterDistance`
`ParameterTableField`           | `QgsProcessingParameterField`
`ParameterXxx`                  | `QgsProcessingParameterXxx`
`QgsFeature.setFeatureId()`     | `QgsFeature.setId()`
`QgsGeometry.fromPoint()`       | `QgsGeometry.fromPointXY()`
`QgsGeometry.fromPolyline()`    | `QgsGeometry.fromPolylineXY()`
`QgsGeometry.fromPolygon()`     | `QgsGeometry.fromPolygonXY()`
`ProcessingLog.addToLog()`      | `QgsProcessingFeedback.pushInfo()` or `QgsProcessingFeedback.pushConsoleInfo()` or `QgsProcessingFeedback.pushDebugInfo()`
`progress.setText()`            | `feedback.pushInfo()`
`progress.setPercentage()`      | `feedback.setProgress()`
`self.getParameterValue(name)`  | `self.parameterAsType(parameters, name, context)`
`v.getFeatures(...).next()`     | `s = context.getMapLayer(v.sourceName())` puis `s.getFeature(fid)`


## Ajouter des tests unitaires