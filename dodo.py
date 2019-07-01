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
import getpass
from lxml import etree
from copy import deepcopy
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

# DOIT tasks

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
        'task_dep': ['uninstall'],
        'verbosity': 2
    }

def task_clean_install():
    """
    Clean build files before installing
    """

    return {
        'actions': [],
        'task_dep': ['clean_build', 'install'],
        'verbosity': 1
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
            'python -m fct.cli.autodoc build'
        ],
        'task_dep': ['doc_clean']
    }

def task_doc_toc():
    """
    Print documentation Table of Content
    """

    return {
        'actions': [
            LongRunning('python -m fct.cli.autodoc toc')
        ],
        'verbosity': 2
    }

def task_doc_serve():
    """
    Start MkDocs developement server
    """

    return {
        'actions': [
            LongRunning('python -m mkdocs serve')
        ],
        'task_dep': ['doc']
    }

def task_doc_deploy():
    """
    Deploy documentation to GitHub Pages
    """

    return {
        'actions': [
            LongRunning('python -m mkdocs gh-deploy')
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
            (copyfiles, ('alien', os.path.join(fct_target_folder(), 'lib'))),
            make_plugin_zip
        ],
        'task_dep': ['clean_build', 'install'],
        'verbosity': 2
    }

def task_releases_stats():
    """
    Get releases download counts
    """

    def get_releases_stats():

        try:

            from github import Github
            g = Github()
            fct_repo = g.get_repo("tramebleue/fct")

            print(" Publish date  | Release tag |           Release title           |            Asset name             | Download count")
            print("---------------|-------------|-----------------------------------|-----------------------------------|---------------")

            for rel in fct_repo.get_releases():
                for asset in rel.get_assets():

                    date = rel.published_at.strftime("%y-%m-%d %H:%M")
                    tag = rel.tag_name
                    title = rel.title[:35]
                    aname = asset.name[:35]
                    c = asset.download_count

                    print(f"{date:^15}|{tag:^13}|{title:^35}|{aname:^35}|{c:^15}")

        except ImportError as error:
            print(str(error))

    return {
        'actions': [
            get_releases_stats
        ],
        'verbosity': 2
    }

def task_release():
    """
    Release new plugin version to github
    """

    def release_plugin():
        """
        Release new plugin version to github
        """

        config = ConfigParser()
        with open(os.path.join('fct', 'metadata.txt')) as f:
            config.read_file(f)

        version = config['general']['version']
        changelog = config['general']['changelog']

        print(f"\nActual dev version: {version}")
        print(f"Actual changelog :{changelog}")

        confirm = input("\nMake new release with this version ? [yes/no] ")

        if confirm == "yes":

            try:
                from github import Github

            except ImportError as error:
                print(str(error))

            user = input("GitHub username: ")
            psswd = getpass.getpass("GitHub password: ")

            g = Github(user, psswd)
            fct_repo = g.get_repo("tramebleue/fct")

            tag_name = f"v{version}"
            zip_path = os.path.join("release", 
                f"FluvialCorridorToolbox.{version}.zip")

            release_name = input("Release name: ")
            prerelease = input("Pre-release tag [True/False]: ")
            if prerelease == "True":
                prerelease = True
            elif prerelease == "False":
                prerelease = False
            else:
                print("Pre-release tag have to be True or False")
                return

            print("make new release...")
            new_release = fct_repo.create_git_release(
                tag=tag_name, 
                name=release_name, 
                message=changelog, 
                prerelease=prerelease) 

            print("upload zip file...")
            zip_asset = new_release.upload_asset(zip_path)
            print(f"version {version} successfully released !")

            print("update plugin repository...")  
            xml_path = os.path.join("docs", "repo", "plugins.xml")
            repo_tree = etree.parse(xml_path)
            last_item = repo_tree.xpath("/plugins/pyqgis_plugin")[0]
            new_item = deepcopy(last_item)

            new_item.attrib['version'] = version
            new_item.attrib['plugin_id'] = str(int(new_item.attrib['plugin_id']) + 1)
            new_item.find("version").text = version
            new_item.find("file_name").text = zip_asset.name
            new_item.find("download_url").text = zip_asset.browser_download_url
            new_item.find("uploaded_by").text = f"<![CDATA[{user}]]>"
            new_item.find("create_date").text = new_release.created_at.strftime("%Y-%m-%d")
            new_item.find("update_date").text = new_release.created_at.strftime("%Y-%m-%d")

            last_item.addprevious(new_item)

            repo_tree.write(xml_path)

            print("update plugin metadata...")
            new_version = input("New dev version tag (e.g.: 1.0.5): ")
            config['general']['version'] = new_version

            new_changelog = input("New changelog item for this version (e.g.: Actual dev version): - ")
            config['general']['changelog'] = f"\n{new_version}\n - {new_changelog}\n{changelog}"

            with open(os.path.join('fct', 'metadata.txt'), 'w') as f:
                config.write(f)

            print("Release done. Warning! Please run doit doc_deploy to update the plugin repository on the github page")

    return {
        'actions': [
            release_plugin
        ],
        'task_dep': ['zip', 'releases_stats'],
        'verbosity': 2
    }