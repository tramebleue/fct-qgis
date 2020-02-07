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
import platform
import warnings
import click

from qgis.core import (
    QgsApplication,
    QgsProcessingException,
    QgsProcessingFeedback,
    QgsProcessingParameterDefinition
)

from qgis.analysis import QgsNativeAlgorithms

from processing.core.Processing import Processing

from fct.FluvialCorridorToolbox import (
    PROVIDERS,
    FluvialCorridorToolboxProvider,
    FluvialCorridorWorkflowsProvider
)

from .helpers import (
    start_app,
    execute_algorithm
)

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
            if instance:
                command = AlgorithmCommand(provider, instance)
                ctx.info_name = command.name
                ctx.command = command
                click.echo(ctx.get_help())
            else:
                click.secho('%s not found' % algorithm, fg='red')
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

        if hasattr(algorithm, 'METADATA'):
            metadata = algorithm.METADATA
            summary = unindent(metadata.get('summary', algorithm.__doc__ or ''))
        else:
            summary = algorithm.shortDescription()

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
                results = AlgorithmCommand.execute(algorithm.id(), **parameters)
                click.echo(results)
            except QgsProcessingException as error:
                click.secho(str(error), fg='red', err=True)

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
    def execute(algorithm_id, **parameters):
        """
        Execute `algorithm` with `parameters'.
        Raise QgsProcessingException on processing error.
        """

        app = start_app(cleanup=False)
        # We have to keep a reference to provider objects
        providers = [cls() for cls in PROVIDERS]
        providers.append(QgsNativeAlgorithms())
        
        for provider in providers:
            QgsApplication.processingRegistry().addProvider(provider)

        click.secho(f'Running <{algorithm_id}>', fg='cyan')
        for parameter in parameters:
            click.echo('{}\t{}'.format(parameter, parameters[parameter]))

        return execute_algorithm(algorithm_id, **parameters)

# @click.command()
# @click.argument('toolbox')
# @click.argument('groups', nargs=-1)
# def list_algorithms(toolbox, groups):

#     start_app()
#     for provider_cls in PROVIDERS:
#         QgsApplication.processingRegistry().addProvider(provider_cls())

#     provider = QgsApplication.processingRegistry().providerById(toolbox)

#     for group in groups:

#         for alg in provider.algorithms():
#             if alg.groupId() == group:
#                 click.echo(alg.name() + "\t" + alg.shortDescription())

#     else:

#         groups = {(alg.groupId(), alg.group()) for alg in provider.algorithms()}
#         for group_id, group_name in groups:
#             click.echo(group_id + "\t" + group_name)


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

        # if name == 'list':
        #     return list_algorithms

        if name == 'help':
            return AlgorithmHelp(self.provider)

        algorithm = self.provider.algorithm(name)
        if algorithm:
            return AlgorithmCommand(self.provider, algorithm) if algorithm else None

        return None

def fct():

    # with warnings.catch_warnings():
    warnings.simplefilter("ignore")

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()

    commands = AlgorithmProviderCommands('fct', provider)

    commands()

def workflows():

    # with warnings.catch_warnings():
    warnings.simplefilter("ignore")

    provider = FluvialCorridorWorkflowsProvider()
    provider.loadAlgorithms()

    commands = AlgorithmProviderCommands('fcw', provider)

    commands()