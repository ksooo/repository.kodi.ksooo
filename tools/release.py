#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#  Copyright (C) 2026 ksooo
#  This file is part of ksooo's Kodi add-on repository
#
#  SPDX-License-Identifier: GPL-2.0-or-later
#  See LICENSE.txt for more information.
#
"""Release one add-on.

Call this from the checkout of the add-on to release, with the new version
already committed in its addon.xml. It tags HEAD with the version that
addon.xml declares, pushes the branch and the tag, asks the repository
workflow to rebuild, and waits until the new version shows up in the
published index.

Needs the gh CLI, logged in to the account that owns this repository.

Usage: python3 tools/release.py [ADD-ON DIRECTORY]

The repository add-on lives in this repository rather than in one of its own,
so release it by naming its directory:

    python3 tools/release.py src/repository.kodi.ksooo
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKFLOW = 'Build repository'

TIMEOUT = 5 * 60
INTERVAL = 15


def git(*arguments, cwd):
    """Run git in the given directory and return its output."""
    return subprocess.run(('git',) + arguments, cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def repository_slug():
    """Return the owner/name this repository has on GitHub."""
    url = git('remote', 'get-url', 'origin', cwd=ROOT).removesuffix('.git')
    if ':' in url and '//' not in url:
        return url.split(':', 1)[1]
    return '/'.join(url.split('/')[-2:])


def published_version(slug, addon_id):
    """Return the version the published index lists for the given add-on."""
    owner, name = slug.split('/')

    # The query string dodges the CDN in front of GitHub Pages, which would
    # otherwise keep answering with the previous index for ten minutes.
    url = 'https://{}.github.io/{}/addons.xml?t={}'.format(owner, name, time.time())
    with urllib.request.urlopen(url, timeout=30) as response:
        index = ElementTree.fromstring(response.read())

    for addon in index:
        if addon.get('id') == addon_id:
            return addon.get('version')
    return None


def check(addon_directory, addon_id, tag):
    """Refuse to release anything but a clean, pushable, untagged state."""
    # The same two sources build_repo.py publishes from: the add-ons cloned
    # per addons.json, and the ones living in src/ - which is where the
    # repository add-on itself sits.
    with open(os.path.join(ROOT, 'addons.json'), 'r', encoding='utf-8') as stream:
        published = [entry['id'] for entry in json.load(stream)['addons']]
    published += os.listdir(os.path.join(ROOT, 'src'))
    if addon_id not in published:
        raise SystemExit('{} is neither listed in addons.json nor present in src/, '
                         'releasing it would publish nothing'.format(addon_id))

    if git('status', '--porcelain', cwd=addon_directory):
        raise SystemExit('{}: commit or stash your changes first'.format(addon_id))

    branch = git('rev-parse', '--abbrev-ref', 'HEAD', cwd=addon_directory)
    if branch == 'HEAD':
        raise SystemExit('{}: HEAD is detached, check out a branch first'.format(addon_id))

    git('fetch', '--quiet', 'origin', cwd=addon_directory)
    if git('rev-list', '--count', 'HEAD..origin/{}'.format(branch), cwd=addon_directory) != '0':
        raise SystemExit('{}: {} is behind origin, pull first'.format(addon_id, branch))

    if (git('tag', '--list', tag, cwd=addon_directory) or
            git('ls-remote', '--tags', 'origin', tag, cwd=addon_directory)):
        raise SystemExit('{}: {} exists already - raise the version in addon.xml'
                         .format(addon_id, tag))

    return branch


def main():
    addon_directory = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')

    addon = ElementTree.parse(os.path.join(addon_directory, 'addon.xml')).getroot()
    addon_id = addon.get('id')
    version = addon.get('version')
    tag = 'v{}'.format(version)

    branch = check(addon_directory, addon_id, tag)

    print('{}: tagging {} as {} and pushing it'.format(addon_id, branch, tag))
    git('tag', '--annotate', tag, '--message', version, cwd=addon_directory)
    git('push', '--quiet', 'origin', branch, cwd=addon_directory)
    git('push', '--quiet', 'origin', tag, cwd=addon_directory)

    slug = repository_slug()
    print('{}: asking it to rebuild'.format(slug))
    subprocess.run(['gh', 'workflow', 'run', WORKFLOW, '--repo', slug], check=True)

    deadline = time.time() + TIMEOUT
    while time.time() < deadline:
        time.sleep(INTERVAL)
        try:
            current = published_version(slug, addon_id)
        except (urllib.error.URLError, ElementTree.ParseError) as error:
            print('  the index is not readable yet ({})'.format(error))
            continue

        if current == version:
            print('{} {} is published'.format(addon_id, version))
            return 0
        print('  the index still lists {}'.format(current))

    raise SystemExit('{} {} has not appeared in the index - see '
                     'https://github.com/{}/actions'.format(addon_id, version, slug))


if __name__ == '__main__':
    sys.exit(main())
