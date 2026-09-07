#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of ksooo's Kodi add-on repository
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Build the servable add-on repository.

The result is the layout Kodi expects: an addons.xml index next to one
directory per add-on, holding <id>-<version>.zip and the assets the add-on
declares. Everything Kodi verifies gets a sibling .sha256 file, because
GitHub Pages sends no content digest headers.

Which add-ons to include comes from addons.json: per add-on its "id", the
clone "url" and the git "ref" to publish - either a fixed tag, or "latest"
to publish the highest version tag the add-on repository has. The repository
add-on itself is built from src/ in the working tree.

Usage: python3 tools/build_repo.py [--output DIRECTORY]
"""

import argparse
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directory names that never belong into an archive, at any depth.
EXCLUDED_DIRECTORIES = frozenset(('.git', '__pycache__'))

#: Development material, only matched at the top level of an add-on, where
#: these names cannot collide with a package of the add-on itself.
EXCLUDED_TOP_LEVEL_DIRECTORIES = frozenset(('.github', 'tests', 'tools'))

EXCLUDED_FILES = frozenset(('.DS_Store', '.gitattributes', '.gitignore'))
EXCLUDED_SUFFIXES = ('.pyc', '.pyo', '.tmp')

#: One fixed timestamp for every archive member, so a given add-on version
#: always builds into a byte identical zip with a stable hash.
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)

LANDING_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ksooo's Kodi Add-ons</title>
<style>
body {{ margin: 0 auto; padding: 2rem 1.5rem; max-width: 46rem;
       font: 16px/1.6 system-ui, sans-serif; color: #16202a; background: #fbfcfd; }}
h1 {{ font-size: 1.6rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ padding: .5rem .75rem; text-align: left; border-bottom: 1px solid #dde3e9;
          vertical-align: top; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #e7edf3; background: #131a21; }}
  th, td {{ border-bottom-color: #2a353f; }}
  a {{ color: #6cd4ff; }}
}}
</style>
</head>
<body>
<h1>ksooo's Kodi Add-ons</h1>
<p>A Kodi add-on repository. To use it, download
<a href="{repository_archive}">{repository_archive}</a>, then in Kodi allow
<em>Settings &rsaquo; System &rsaquo; Add-ons &rsaquo; Unknown sources</em> and install the file
via <em>Add-ons &rsaquo; Install from zip file</em>. The add-ons below are then available under
<em>Add-ons &rsaquo; Install from repository</em>, and Kodi keeps them up to date on its own.</p>
<h2>Contents</h2>
<table>
<tr><th>Add-on</th><th>Version</th><th>Description</th></tr>
{rows}
</table>
<p>Index: <a href="addons.xml">addons.xml</a> (<a href="addons.xml.sha256">sha256</a>).
Sources: <a href="https://github.com/ksooo/repository.kodi.ksooo">github.com/ksooo/repository.kodi.ksooo</a>.</p>
</body>
</html>
"""


def collect(addon_directory):
    """Return the add-on relative paths of everything belonging into the archive."""
    collected = []
    for root, directories, files in os.walk(addon_directory):
        excluded = EXCLUDED_DIRECTORIES
        if os.path.samefile(root, addon_directory):
            excluded = excluded | EXCLUDED_TOP_LEVEL_DIRECTORIES
        directories[:] = sorted(d for d in directories if d not in excluded)

        for name in sorted(files):
            if name in EXCLUDED_FILES or name.endswith(EXCLUDED_SUFFIXES):
                continue
            collected.append(os.path.relpath(os.path.join(root, name), addon_directory))
    return collected


def metadata_extension(addon):
    """Return the metadata extension element of the given addon.xml root."""
    for extension in addon.findall('extension'):
        if extension.get('point', '').endswith('addon.metadata'):
            return extension
    return None


def declared_assets(addon):
    """Return the asset paths the given addon.xml root declares."""
    extension = metadata_extension(addon)
    if extension is None:
        return []
    return [asset.text.strip() for asset in extension.findall('assets/*') if asset.text]


def summary(addon):
    """Return the English summary of the given addon.xml root."""
    extension = metadata_extension(addon)
    if extension is None:
        return ''
    for element in extension.findall('summary'):
        if element.get('lang', '').startswith('en') and element.text:
            return element.text.strip()
    return ''


def version_of(tag):
    """Return the sortable version of a v<major>.<minor>.<patch> tag, or None."""
    if not tag.startswith('v'):
        return None

    parts = tag[1:].split('.')
    if not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def latest_tag(url):
    """Return the highest version tag of the given repository."""
    listing = subprocess.run(['git', 'ls-remote', '--tags', '--refs', url],
                             check=True, capture_output=True, text=True).stdout
    tags = [tag for tag in (line.rsplit('/', 1)[-1] for line in listing.splitlines())
            if version_of(tag) is not None]
    if not tags:
        raise SystemExit('{} has no version tag to publish'.format(url))
    return max(tags, key=version_of)


def write_sha256(path):
    """Write the digest file Kodi falls back to when no digest header arrives."""
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 16), b''):
            digest.update(block)

    # sha256sum format: Kodi cuts the value at the first space, and sha256sum -c
    # can check the file as it is.
    with open(path + '.sha256', 'w', encoding='utf-8', newline='\n') as stream:
        stream.write('{}  {}\n'.format(digest.hexdigest(), os.path.basename(path)))


def build_addon(addon_directory, output_directory, expected_id, expected_version=None):
    """Package one add-on into the output tree and return its addon.xml root."""
    addon = ElementTree.parse(os.path.join(addon_directory, 'addon.xml')).getroot()
    addon_id = addon.get('id')
    version = addon.get('version')
    if addon_id != expected_id:
        raise SystemExit('expected the add-on {}, but its addon.xml declares {}'
                         .format(expected_id, addon_id))
    if expected_version is not None and version != expected_version:
        raise SystemExit('{}: the tag says version {}, but its addon.xml says {} - raise the '
                         'version in addon.xml, or move the tag'
                         .format(addon_id, expected_version, version))

    target_directory = os.path.join(output_directory, addon_id)
    os.makedirs(target_directory)

    archive_path = os.path.join(target_directory, '{}-{}.zip'.format(addon_id, version))
    with zipfile.ZipFile(archive_path, 'w') as archive:
        for relative_path in collect(addon_directory):
            # Kodi wants a single top level directory named exactly like the add-on id.
            name = '/'.join([addon_id] + relative_path.split(os.sep))
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(os.path.join(addon_directory, relative_path), 'rb') as stream:
                archive.writestr(info, stream.read())
    write_sha256(archive_path)

    # Icons and screenshots are read from <artdir>/<id>/, not out of the archive.
    for asset in declared_assets(addon):
        source = os.path.join(addon_directory, asset.replace('/', os.sep))
        if not os.path.isfile(source):
            raise SystemExit('{}: the declared asset {} does not exist'.format(addon_id, asset))
        target = os.path.join(target_directory, asset.replace('/', os.sep))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(source, target)

    print('{} {}'.format(addon_id, version))
    return addon


def write_index(addons, output_directory):
    """Write the addons.xml index of the given addon.xml roots."""
    index = ElementTree.Element('addons')
    index.extend(sorted(addons, key=lambda addon: addon.get('id')))
    ElementTree.indent(index, space='  ')

    path = os.path.join(output_directory, 'addons.xml')
    ElementTree.ElementTree(index).write(path, encoding='UTF-8', xml_declaration=True)
    write_sha256(path)


def write_landing_page(addons, repository_id, output_directory):
    """Write an index page, so that the repository URL is useful in a browser too."""
    rows = []
    for addon in sorted(addons, key=lambda addon: addon.get('id')):
        addon_id = addon.get('id')
        version = addon.get('version')
        archive = '{0}/{0}-{1}.zip'.format(addon_id, version)
        if addon_id == repository_id:
            repository_archive = archive
        rows.append('<tr><td><a href="{}">{}</a></td><td>{}</td><td>{}</td></tr>'.format(
            archive, html.escape(addon.get('name')), html.escape(version),
            html.escape(summary(addon))))

    with open(os.path.join(output_directory, 'index.html'), 'w',
              encoding='utf-8', newline='\n') as stream:
        stream.write(LANDING_PAGE.format(repository_archive=repository_archive,
                                         rows='\n'.join(rows)))


def main():
    parser = argparse.ArgumentParser(description='Build the servable add-on repository.')
    parser.add_argument('--output', default=os.path.join(ROOT, 'public'),
                        help='directory to write the repository into (default: ./public)')
    arguments = parser.parse_args()

    output_directory = os.path.abspath(arguments.output)
    if os.path.isdir(output_directory):
        shutil.rmtree(output_directory)
    os.makedirs(output_directory)

    source_directory = os.path.join(ROOT, 'src')
    repository_ids = sorted(os.listdir(source_directory))
    addons = [build_addon(os.path.join(source_directory, name), output_directory, name)
              for name in repository_ids]

    with open(os.path.join(ROOT, 'addons.json'), 'r', encoding='utf-8') as stream:
        configuration = json.load(stream)

    with tempfile.TemporaryDirectory() as scratch:
        for entry in configuration['addons']:
            ref = entry['ref']
            if ref == 'latest':
                ref = latest_tag(entry['url'])
                print('{}: the highest version tag is {}'.format(entry['id'], ref))

            checkout = os.path.join(scratch, entry['id'])
            # Checking out a tag detaches HEAD, which git is chatty about.
            subprocess.run(['git', '-c', 'advice.detachedHead=false', 'clone', '--quiet',
                            '--depth', '1', '--branch', ref, entry['url'], checkout], check=True)
            tag_version = version_of(ref)
            addons.append(build_addon(checkout, output_directory, entry['id'],
                                      ref[1:] if tag_version is not None else None))

    write_index(addons, output_directory)
    write_landing_page(addons, repository_ids[0], output_directory)
    return 0


if __name__ == '__main__':
    sys.exit(main())
