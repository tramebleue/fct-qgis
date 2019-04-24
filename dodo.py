# -*- coding: utf-8 -*-

"""
Build tools, cross-platform replacement for Makefile

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
import platform
import shutil
from configparser import ConfigParser
from doit.tools import LongRunning

DOIT_CONFIG = {
    'default_tasks': ['install']
}

def qgis_user_dir():

    if 'QGIS_USER_DIR' in os.environ:
        return os.environ['QGIS_USER_DIR']

    home = os.path.expanduser('~')

    if platform.system() == 'Darwin':
        return os.path.join(home, 'Library', 'Application Support',
            'QGIS', 'QGIS3', 'profiles', 'default')

    elif platform.system() == 'Windows':
        return os.path.join(home, 'AppData', 'Roaming',
            'QGIS', 'QGIS3', 'profiles', 'default')
    
    else:
        return os.path.join(home, '.local', 'share',
            'QGIS', 'QGIS3', 'profiles', 'default')

def qgis_plugin_dir():
    return os.path.join(qgis_user_dir(), 'python', 'plugins')

def fct_target_folder():
    return os.path.join(qgis_plugin_dir(), 'FluvialCorridorToolbox')

def pyclean(root):
    """
    Delete __pycache__ dirs and *.pyc files
    """

    print('Delete *.pyc files')

    for dirpath, dirnames, filenames in os.walk(root):
        
        for dirname in dirnames:
            if dirname == '__pycache__':
                shutil.rmtree(os.path.join(dirpath, dirname))
        
        for filename in filenames:
            name, ext = os.path.splitext(filename)
            if ext == '.pyc':
                os.remove(os.path.join(dirpath, filename))

def copyfiles(root, destination):
    """
    Copy root/* to destination directory
    """

    print(f'Copy {root}/* to {destination}')

    if not os.path.exists(destination):
        os.makedirs(destination)

    for item in os.listdir(root):

        path = os.path.join(root, item)
        if os.path.isdir(path):
            shutil.copytree(path, os.path.join(destination, item))
        else:
            shutil.copy2(path, destination)

def delete_folder(folder):
    """
    Delete `folder` if it exists
    """

    if os.path.exists(folder):
        
        print(f'Remove directory {folder}')
        shutil.rmtree(folder)

def task_extension():
    """
    Build Cython extension
    """

    return {
        'actions': [
            'pip install -e .'
        ],
        'verbosity': 2
    }

def task_install():
    """
    Install plugin to user's QGis plugin directory
    """

    def copy_extension():
        """
        Copy extension to FluvialCorridorToolbox/lib
        """

        try:

            from fct.lib import terrain_analysis as ta
            src = ta.__file__
            destination = os.path.join(fct_target_folder(), 'lib')
            print('Copy %s to %s' % (src, destination))
            shutil.copy2(src, destination)

        except ImportError as error:
            print(str(error))

    return {
        'actions': [
            (copyfiles, ('fct', fct_target_folder())),
            copy_extension
        ],
        'task_dep': ['uninstall', 'extension'],
        'verbosity': 2
    }

def task_uninstall():
    """
    Delete plugin folder in user's QGis plugin directory
    """

    return {
        'actions': [
            (delete_folder, (fct_target_folder(),))
        ],
        'verbosity': 2
    }

def task_clean_build():
    """
    Clean development files
    """

    return {
        'actions': [
            (pyclean, ('fct',)),
            (delete_folder, ('build',)),
            (delete_folder, (os.path.join('cython', 'build'),))
        ],
        'verbosity': 2
    }


def task_doc():
    """
    Build algorithm documentation from YAML files
    """

    return {
        'actions': [
            'python3 -m fct.cli.autodoc build'
        ],
        'task_dep': ['doc_clean']
    }

def task_doc_toc():
    """
    Print documentation Table of Content
    """

    return {
        'actions': [
            LongRunning('python3 -m fct.cli.autodoc toc')
        ],
        'verbosity': 2
    }

def task_doc_serve():
    """
    Start MkDocs developement server
    """

    return {
        'actions': [
            LongRunning('python3 -m mkdocs serve')
        ],
        'task_dep': ['doc']
    }

def task_doc_deploy():
    """
    Deploy documentation to GitHub Pages
    """

    return {
        'actions': [
            LongRunning('python3 -m mkdocs gh-deploy')
        ],
        'task_dep': ['doc']
    }

def task_doc_clean():
    """
    Clean generated documentation and MkDocs temporary files
    """

    return {
        'actions': [
            (delete_folder, (os.path.join('docs','algorithms'),)),
            (delete_folder, (os.path.join('docs','workflows'),)),
            (delete_folder, ('site',))
        ],
        'verbosity': 2
    }

def task_zip():
    """
    Create a zip archive
    suitable for uploading to the QGIS plugin repository
    """

    def make_plugin_zip():
        """
        Create zip archive in current `release` directory
        """

        config = ConfigParser()
        with open(os.path.join('fct', 'metadata.txt')) as f:
            config.read_file(f)

        version = config['general']['version']

        shutil.make_archive(
            os.path.join('release', 'FluvialCorridorToolbox.' + version),
            'zip',
            qgis_plugin_dir(),
            'FluvialCorridorToolbox'
        )

    return {
        'actions': [
            make_plugin_zip
        ],
        'task_dep': ['clean_build', 'install'],
        'verbosity': 2
    }
