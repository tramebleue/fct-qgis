# -*- coding: utf-8 -*-

"""
Start QGis Application Helper
Adapted from qgis.testing

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

import os
import sys
import platform
import atexit
import click

from qgis.core import ( # pylint: disable=import-error,no-name-in-module
    QgsApplication,
    QgsProcessingException,
    QgsProcessingFeedback
)

from processing.core.Processing import ( # pylint: disable=import-error,no-name-in-module
    Processing
)

from processing.tools.dataobjects import ( # pylint: disable=import-error,no-name-in-module
    createContext
)

def execute_algorithm(algorithm_id, **parameters):

    algorithm = QgsApplication.processingRegistry().createAlgorithmById(algorithm_id)

    feedback = QgsProcessingFeedback()
    context = createContext(feedback)

    parameters_ok, msg = algorithm.checkParameterValues(parameters, context)
    if not parameters_ok:
        raise QgsProcessingException(msg)

    if not algorithm.validateInputCrs(parameters, context):
        feedback.reportError(
            Processing.tr('Warning: Not all input layers use the same CRS.\nThis can cause unexpected results.'))

    results, execution_ok = algorithm.run(parameters, context, feedback)

    if execution_ok:
        return results
    else:
        msg = Processing.tr("There were errors executing the algorithm.")
        raise QgsProcessingException(msg)

def start_app(gui=True, cleanup=True):
    """
    Will start a QgsApplication and call all initialization code like
    registering the providers and other infrastructure.
    It will not load any plugins.
    You can always get the reference to a running app by calling `QgsApplication.instance()`.
    The initialization will only happen once, so it is safe to call this method repeatedly.

    Parameters
    ----------
    cleanup: Do cleanup on exit. Defaults to true.

    Returns
    -------
    QgsApplication
    A QgsApplication singleton
    """

    global QGISAPP # pylint: disable=global-variable-undefined

    try:
        QGISAPP
    except NameError:

        # In python3 we need to convert to a bytes object (or should
        # QgsApplication accept a QString instead of const char* ?)
        try:
            argvb = [os.fsencode(arg) for arg in sys.argv]
        except AttributeError:
            argvb = ['']

        if platform.system() == 'Darwin':
            QgsApplication.addLibraryPath(os.path.expandvars('$QGIS_PREFIX_PATH/../Plugins'))
            QgsApplication.addLibraryPath(os.path.expandvars('$QGIS_PREFIX_PATH/../Plugins/qgis'))
            QgsApplication.addLibraryPath(os.path.expandvars('$QGIS_PREFIX_PATH/../MacOS'))

        # Note: QGIS_PREFIX_PATH is evaluated in QgsApplication -
        # no need to mess with it here.
        QGISAPP = QgsApplication(argvb, gui)

        QGISAPP.initQgis()
        # click.echo(QGISAPP.showSettings())
        Processing.initialize()

        def debug_log_message(message, tag, level):
            """ Print debug message on console """
            click.secho('{}({}): {}'.format(tag, level, message), fg='yellow')

        QgsApplication.instance().messageLog().messageReceived.connect(debug_log_message)

        if cleanup:

            @atexit.register
            def exitQgis(): # pylint: disable=unused-variable
                """ Exit Qgis Application """
                QGISAPP.exitQgis()

    return QGISAPP
