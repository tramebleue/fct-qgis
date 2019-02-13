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
import click

sys.path.append(os.path.expandvars('$QGIS_PREFIX/share/qgis/python/plugins'))
sys.path.append(os.path.expandvars('$HOME/.local/share/QGIS/QGIS3/profiles/default/python/plugins'))

from qgis.core import (
    QgsProcessingParameterDefinition
)

def unindent(text):
    """
    Remove spaces at beginning of lines.
    """

    return '\n'.join([s.lstrip() for s in text.split('\n')])

def isRequired(p):
    """
    Return False if parameter `p` is optional.
    """
    return int(p.flags() & QgsProcessingParameterDefinition.FlagOptional) == 0

class AlgorithmHelp(click.Command):

    def __init__(self, provider, **kwargs):

        params = [
            click.Argument(['ALGORITHM'], required=True)
        ]

        @click.pass_context
        def callback(ctx, algorithm=None):
            instance = provider.algorithm(algorithm)
            command = AlgorithmCommand(instance)
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

    def __init__(self, algorithm, **kwargs):

        metadata = algorithm.METADATA
        summary = unindent(metadata.get('summary', algorithm.__doc__ or ''))
        params = []

        for param in algorithm.parameterDefinitions():
            params.append(click.Option(
                ['--' + param.name()],
                required=isRequired(param),
                default=param.defaultValue(),
                help=param.description()))

        def callback(*args, **kwargs):
            click.echo('Should be running %s ...' % algorithm.name())
            click.echo(args)
            click.echo(kwargs)

        kwargs.update(
            name=algorithm.name(),
            callback=callback,
            params=params,
            help=summary,
            short_help=algorithm.displayName(),
            add_help_option=True)
            # no_args_is_help=True)

        super().__init__(**kwargs)


class AlgorithmProviderCommands(click.MultiCommand):

    def __init__(self, name, provider, **kwargs):
        kwargs.update(name=name)
        self.provider = provider
        super().__init__(**kwargs)

    def list_commands(self, ctx):
        return ['help', 'autodoc', 'toc', 'parameters'] + sorted([
            a.name()
            for a in self.provider.algorithms()
            if hasattr(a, 'METADATA')
        ])

    def get_command(self, ctx, name):

        if name == 'help':
            return AlgorithmHelp(self.provider)

        if name == 'autodoc':
            from .autodoc import autodoc
            return autodoc

        if name == 'toc':
            from .autodoc import toc
            return toc

        if name == 'parameters':
            from .autodoc import parameters
            return parameters

        algorithm = self.provider.algorithm(name)
        return AlgorithmCommand(algorithm) if algorithm else None
