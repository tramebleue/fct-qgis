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

import os
from collections import defaultdict
import click

# pylint: disable=import-error,no-name-in-module,wrong-import-position

import jinja2
import bleach

from qgis.core import (
    QgsProcessingParameterDefinition
)

from FluvialCorridorToolbox.FluvialCorridorToolbox import FluvialCorridorToolboxProvider

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

def isOptional(p):
    """
    Return True if parameter `p` is optional.
    """
    return int(p.flags() & QgsProcessingParameterDefinition.FlagOptional) > 0

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

    if not os.path.isdir(directory) and not os.path.exists(directory):
        os.mkdir(directory)

    parameters = list()

    for p in alg.parameterDefinitions():
        if 'parameters' in metadata:
            if p.name() in metadata['parameters']:
                param = metadata['parameters'][p.name()].copy()
                param.update(
                    name=p.name(),
                    shortDescription=p.description() or '',
                    defaultValue=p.defaultValue(),
                    optional=isOptional(p))
                parameters.append(param)
        else:
            parameters.append({
                'name': p.name(),
                'shortDescription': p.description() or '',
                'description': '',
                'type': type(p).__name__,
                'defaultValue': p.defaultValue(),
                'optional': isOptional(p)
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
    link_algorithm.algs = algs

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

@click.command()
def toc():
    """
    Print YAML Table of Content
    (index of doc generated doc pages)
    """

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()

    groups = defaultdict(list)
    algs = {a.name(): a for a in provider.algorithms()}
    for alg in algs.values():
        groups[alg.groupId()].append((alg.__class__.__name__, alg.displayName()))

    for group in provider.groups:

        name = provider.groups[group]

        click.echo('- %s:' % name)
        click.echo('  - Index: algorithm/%s/index.md' % group)

        for link, algorithm in sorted(groups[group]):
            click.echo('  - algorithms/%s/%s.md' % (group, link))

@click.command()
@click.argument('names', nargs=-1)
@click.option(
    '--destination',
    type=click.Path(exists=False, file_okay=False),
    default='docs/algorithms',
    help='Output Folder')
def autodoc(names, destination=None):
    """
    Generate Markdown documentation for each algorithms.
    The documentation is generated in directory `docs/algorithms`.
    """

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()

    if names:

        for name in names:
            alg = provider.algorithm(name)
            if alg:
                generate_alg(alg, destination)

    else:

        generate_doc(provider, destination)

@click.command()
@click.argument('algorithm')
def parameters(algorithm):
    """
    List parameters of algorithm with name `name`
    """

    provider = FluvialCorridorToolboxProvider()
    provider.loadAlgorithms()
    algs = {a.name(): a for a in provider.algorithms()}

    if algorithm.lower() in algs:

        alg = algs[algorithm.lower()]

        click.echo(algorithm)
        click.echo('parameters:')

        for parameter in alg.parameterDefinitions():
            click.echo('  ' + parameter.name() + ':')
            click.echo('    type: ' + type(parameter).__name__)
            click.echo('    description: ' + parameter.description())
