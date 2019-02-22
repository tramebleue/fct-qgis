# -*- coding: utf-8 -*-

"""
Click Adapters for Qgis Processing Algorithms

***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""
import sys
import os
import warnings
import click

from qgis.core import (
    QgsApplication,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterDefinition
)

from processing.core.Processing import Processing
from processing.tools.dataobjects import createContext

def unindent(text):
    """
    Remove spaces at beginning of lines.
    """

    return '\n'.join([s.lstrip() for s in text.split('\n')])

def isRequired(parameter):
    """
    Return False if parameter `parameter` is optional.
    """
    return int(parameter.flags() & QgsProcessingParameterDefinition.FlagOptional) == 0

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

        # Note: QGIS_PREFIX_PATH is evaluated in QgsApplication -
        # no need to mess with it here.
        QGISAPP = QgsApplication(argvb, gui)

        QGISAPP.initQgis()
        # click.echo(QGISAPP.showSettings())
        Processing.initialize()

        def debug_log_message(message, tag, level):
            """ Print debug message on console """
            click.echo(click.style('{}({}): {}'.format(tag, level, message), fg='yellow'))

        QgsApplication.instance().messageLog().messageReceived.connect(debug_log_message)

        if cleanup:
            import atexit

            @atexit.register
            def exitQgis(): # pylint: disable=unused-variable
                """ Exit Qgis Application """
                QGISAPP.exitQgis()

    return QGISAPP

class AlgorithmHelp(click.Command):

    def __init__(self, provider, **kwargs):

        params = [
            click.Argument(['ALGORITHM'], required=True)
        ]

        @click.pass_context
        def callback(ctx, algorithm=None):
            """
            Print algorithm's short description and parameters.
            """
            instance = provider.algorithm(algorithm)
            command = AlgorithmCommand(provider, instance)
            ctx.info_name = command.name
            ctx.command = command
            click.echo(ctx.get_help())

        kwargs.update(
            name='help',
            callback=callback,
            params=params,
            help='Print help message for ALGORITHM',
            add_help_option=False)

        super().__init__(**kwargs)

class AlgorithmCommand(click.Command):

    def __init__(self, provider, algorithm, **kwargs):

        metadata = algorithm.METADATA
        summary = unindent(metadata.get('summary', algorithm.__doc__ or ''))
        params = []

        for param in algorithm.parameterDefinitions():
            params.append(click.Option(
                ['--' + param.name()],
                required=isRequired(param),
                default=param.defaultValue(),
                help=param.description()))

        def callback(**kwargs):
            """ Execute algorithm """

            # click.echo('Should be running %s ...' % algorithm.name())
            # click.echo(args)
            parameters = {key.upper(): kwargs[key] for key in kwargs}

            try:
                results = AlgorithmCommand.execute(provider, algorithm.id(), **parameters)
                click.echo(results)
            except QgsProcessingException as error:
                click.echo(click.style(str(error), fg='red'), err=True)

        kwargs.update(
            name=algorithm.name(),
            callback=callback,
            params=params,
            help=summary,
            short_help=algorithm.displayName(),
            add_help_option=True)
            # no_args_is_help=True)

        super().__init__(**kwargs)

    @staticmethod
    def execute(provider, algorithm_id, **parameters):
        """
        Execute `algorithm` with `parameters'.
        Raise QgsProcessingException on processing error.
        """

        start_app()
        QgsApplication.processingRegistry().addProvider(provider)
        algorithm = QgsApplication.processingRegistry().createAlgorithmById(algorithm_id)

        feedback = QgsProcessingFeedback()
        context = createContext(feedback)

        click.echo(click.style(f'Running <{algorithm.displayName()}>', fg='cyan'))
        for parameter in parameters:
            click.echo('{}\t{}'.format(parameter, parameters[parameter]))

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

class AlgorithmProviderCommands(click.MultiCommand):

    def __init__(self, name, provider, **kwargs):
        kwargs.update(name=name)
        self.provider = provider
        super().__init__(**kwargs)

    def list_commands(self, ctx):
        return ['help'] + sorted([
            a.name()
            for a in self.provider.algorithms()
            if hasattr(a, 'METADATA')
        ])

    def get_command(self, ctx, name):

        if name == 'help':
            return AlgorithmHelp(self.provider)

        algorithm = self.provider.algorithm(name)
        return AlgorithmCommand(self.provider, algorithm) if algorithm else None

def cli():

    # with warnings.catch_warnings():
    warnings.simplefilter("ignore")

    from fct.FluvialCorridorToolbox import FluvialCorridorToolboxProvider

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()

    commands = AlgorithmProviderCommands('fct', provider)

    commands()
