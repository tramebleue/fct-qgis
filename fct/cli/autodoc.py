# -*- coding: utf-8 -*-

"""
Generate algorithm reference documentation
from YAML metadata in the source code.

The documentation is generated in directory `docs/algorithms`.

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
from collections import defaultdict
from itertools import chain
import click

# pylint: disable=import-error,no-name-in-module,wrong-import-position

import jinja2
import bleach

from qgis.core import (
    QgsProcessingParameterDefinition,
    QgsProcessingModelAlgorithm
)

from fct.FluvialCorridorToolbox import PROVIDERS

def link_algorithm(item):

    if item.lower() in link_algorithm.algs:
        target = link_algorithm.algs[item.lower()]
        link = '../../%s/%s' % (target.groupId(), type(target).__name__)
        return jinja2.Markup('<a href="%s">%s</a>' % (link, target.displayName()))
    else:
        return item

def fieldlist(fields):
    """
    Format list of field descriptions.
    """

    if not fields:
        return ''

    buf = list()

    for field in fields:
        if isinstance(field, dict):
            for name, description in field.items():
                buf.append('<code>%s</code>: %s' % (name, description))
        else:
            buf.append(field)

    return jinja2.Markup('<ul><li>' + '</li><li>'.join(buf) + '</li></ul>')


# import markdown
# md = markdown.Markdown(extensions=[
#     'abbr',
#     'admonition',
#     'footnotes',
#     'nl2br',
#     'sane_lists',
#     'smarty'
# ])

loader = jinja2.FileSystemLoader(searchpath="./templates")
environment = jinja2.Environment(loader=loader)
# environment.filters['markdown'] = lambda text: jinja2.Markup(md.convert(text))
environment.filters['nl2br'] = lambda text: jinja2.Markup(text.replace('\n', '</br>\n'))
environment.filters['link_algorithm'] = link_algorithm
environment.filters['linkify'] = bleach.linkify
environment.filters['fieldlist'] = fieldlist

ALGORITHM_TEMPLATE = environment.get_template('algorithm.md')
GROUP_TEMPLATE = environment.get_template('group.md')

def unindent(text):
    """
    Remove spaces at beginning of lines.
    """

    return '\n'.join([s.lstrip() for s in text.split('\n')])

def isOptional(parameter):
    """
    Return True if parameter `p` is optional.
    """
    if isinstance(parameter, QgsProcessingParameterDefinition):
        return int(parameter.flags() & QgsProcessingParameterDefinition.FlagOptional) > 0
    return False

def default_value(parameter):
    """
    Return parameter's default value,
    or None if it is an output parameter.
    """
    if isinstance(parameter, QgsProcessingParameterDefinition):
        return parameter.defaultValue()
    return None

def model_outputs(alg):
    """
    List model's output parameters
    """

    output_parameters = dict()

    for child in alg.childAlgorithms():
        output_parameters.update(alg.childAlgorithm(child).modelOutputs())

    return output_parameters

def generate_alg(alg, destination):
    """
    Generate Markdown documentation for algorithm `alg`.
    """

    if not hasattr(alg, 'METADATA'):
        return

    metadata = alg.METADATA.copy()
    group = metadata['group']
    directory = os.path.join(destination, group)
    key = alg.__class__.__name__
    filename = os.path.join(directory, key + '.md')

    click.echo(click.style('Generating file %s' % filename, fg='green'))

    if not os.path.isdir(directory) and not os.path.exists(directory):
        os.mkdir(directory)

    parameters = list()
    seen_parameters = set()

    for parameter in chain(alg.parameterDefinitions(), alg.outputDefinitions()):

        if 'parameters' in metadata:

            if parameter.name() in metadata['parameters']:
                name = parameter.name()
            elif parameter.description() in metadata['parameters']:
                name = parameter.description()
            else:
                continue

            if name in seen_parameters:
                continue

            param = metadata['parameters'][name].copy()
            param.update(
                name=name,
                shortDescription=parameter.description() or '',
                defaultValue=default_value(parameter),
                optional=isOptional(parameter))
            parameters.append(param)

            seen_parameters.add(name)

        else:

            name = parameter.name()

            if name in seen_parameters:
                continue

            parameters.append({
                'name': name,
                'shortDescription': parameter.description() or '',
                'description': '',
                'type': type(parameter).__name__,
                'defaultValue': default_value(parameter),
                'optional': isOptional(parameter)
            })

            seen_parameters.add(name)

    if isinstance(alg, QgsProcessingModelAlgorithm):

        for name, parameter in model_outputs(alg).items():

            if 'parameters' in metadata and name in metadata['parameters']:

                param = metadata['parameters'][name].copy()
                param.update(
                    name=name,
                    shortDescription=parameter.description() or '',
                    optional=False)
                parameters.append(param)

            else:

                parameters.append({
                    'name': name,
                    'shortDescription': parameter.description() or '',
                    'description': '',
                    'type': type(parameter).__name__,
                    'optional': False
                })

    summary = metadata.get('summary', alg.__doc__)

    metadata.update(
        summary=unindent(summary or ''),
        description=metadata.get('description', None) or 'No Description Yet.',
        parameters=parameters,
        tags=[tag for tag in metadata.get('tags', [])])

    with open(filename, 'w') as output:
        output.write(ALGORITHM_TEMPLATE.render(metadata))

def generate_doc(provider, destination='docs/algorithms'):
    """
    Generate Markdown documentation for each algorithms.
    The documentation is generated in directory `docs/algorithms`.
    """

    groups = defaultdict(list)
    algs = {a.name(): a for a in provider.algorithms()}

    if not os.path.isdir(destination) and not os.path.exists(destination):
        os.mkdir(destination)

    for alg in algs.values():

        generate_alg(alg, destination)
        groups[alg.groupId()].append((alg.__class__.__name__, alg.displayName()))

    for group in provider.groups:

        name = provider.groups[group]
        filename = os.path.join(destination, group, 'index.md')
        with open(filename, 'w') as output:
            output.write(GROUP_TEMPLATE.render({
                'group': name,
                'algorithms': groups[group]
            }))

def get_provider(path):
    """
    Return AlgorithmProvider matchin `path`
    """

    for folder, provider_cls in PROVIDERS:
        if path == folder:
            return provider_cls()

def watch_directory(directory, destination):
    """
    Watch `directory` for file modification,
    and regenerate documentation as needed.
    """

    try:
        import pyinotify
        import asyncio
    except ImportError:
        return

    def handle_event(event):
        """
        Handle file modification event
        -> regenerate algorithm doc
        """

        name, ext = os.path.splitext(event.name)
        folder, algname = os.path.split(name)

        if ext == '.yml' or ext == '.py':
            provider = get_provider(folder)
            provider.loadAlgorithms()
            algs = {a.name(): a for a in provider.algorithms()}
            link_algorithm.algs = algs
            alg = provider.algorithm(name.lower())

            if alg:
                generate_alg(alg, destination=os.path.join(destination, folder))

    manager = pyinotify.WatchManager()
    flag = pyinotify.IN_CREATE | pyinotify.IN_DELETE | pyinotify.IN_MODIFY
    manager.add_watch(directory, flag, rec=True, do_glob=True, auto_add=True)

    loop = asyncio.get_event_loop()
    notifier = pyinotify.AsyncioNotifier(manager, loop, default_proc_fun=handle_event)

    try:
        loop.run_forever()
    except:
        pass
    finally:
        notifier.stop()

@click.group()
def autodoc():
    pass

@autodoc.command()
def toc():
    """
    Print YAML Table of Content
    (index of doc generated pages)
    """

    for folder, provider_cls in PROVIDERS:

        provider = provider_cls()
        provider.loadAlgorithms()

        groups = defaultdict(list)
        algs = {a.name(): a for a in provider.algorithms()}
        for alg in algs.values():
            groups[alg.groupId()].append((alg.__class__.__name__, alg.displayName()))

        for group in provider.groups:

            name = provider.groups[group]

            click.echo('- %s:' % name)
            click.echo('  - Index: %s/%s/index.md' % (folder, group))

            for link, algorithm in sorted(groups[group]):
                click.echo('  - %s/%s/%s.md' % (folder, group, link))

@autodoc.command()
@click.argument('names', nargs=-1)
@click.option(
    '--destination',
    type=click.Path(exists=False, file_okay=False),
    default='docs',
    help='Output Folder')
@click.option(
    '--watch/--no-watch',
    default=False,
    help='Watch for file modification')
@click.option(
    '--watch-dir',
    type=click.Path(exists=True, file_okay=False),
    default='fct',
    help='Directory to watch for modification')
def build(names, destination=None, watch=False, watch_dir=None):
    """
    Generate Markdown documentation for each algorithms.
    The documentation is generated in directory `docs/algorithms`.
    """

    for folder, provider_cls in PROVIDERS:
        
        provider = provider_cls()
        provider.loadAlgorithms()

        algs = {a.name(): a for a in provider.algorithms()}
        link_algorithm.algs = algs

        if names:

            for name in names:
                alg = provider.algorithm(name)
                if alg:
                    generate_alg(alg, os.path.join(destination, folder))

        else:

            generate_doc(provider, os.path.join(destination, folder))

    if watch and watch_dir:

        click.echo(click.style('Start watching %s for modification ...' % watch_dir, fg='yellow'))
        watch_directory(watch_dir, destination)
        click.echo('\nDone.')

@autodoc.command()
@click.argument('algorithm')
def parameters(algorithm):
    """
    List parameters of algorithm with name `name`
    """

    for folder, provider_cls in PROVIDERS:

        provider = provider_cls()
        provider.loadAlgorithms()
        algs = {a.name(): a for a in provider.algorithms()}

        if algorithm.lower() in algs:

            alg = algs[algorithm.lower()]

            click.echo(algorithm)
            click.echo('parameters:')

            seen_parameters = set()

            for parameter in chain(alg.parameterDefinitions(), alg.outputDefinitions()):

                if parameter.name() in seen_parameters:
                    continue

                click.echo('  ' + parameter.name() + ':')
                click.echo('    type: ' + type(parameter).__name__)
                click.echo('    description: ' + parameter.description())

                seen_parameters.add(parameter.name())

            if isinstance(alg, QgsProcessingModelAlgorithm):
                for parameter in model_outputs(alg).values():
                    click.echo('  ' + parameter.name() + ':')
                    click.echo('    type: ' + type(parameter).__name__)
                    click.echo('    description: ' + parameter.description())

if __name__ == '__main__':
    autodoc()
