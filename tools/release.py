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

A binary add-on keeps its addon.xml.in in a directory named like its id. For
it, the add-on's own release workflow builds the zips the index points to,
and this waits for it before the repository rebuilds.

Usage: python3 tools/release.py [ADD-ON DIRECTORY]

The repository add-on lives in this repository rather than in one of its own,
so release it by naming its directory:

    python3 tools/release.py src/repository.kodi.ksooo
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ElementTree

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORKFLOW = 'Build repository'
RELEASE_WORKFLOW = 'release.yml'

TIMEOUT = 5 * 60
INTERVAL = 15


def run(*command, cwd=None):
    """Run a command and return its output, or stop with the error it reported."""
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit('{} failed:\n{}'.format(' '.join(command), result.stderr.strip()))
    return result.stdout.strip()


def git(*arguments, cwd):
    """Run git in the given directory and return its output."""
    return run('git', *arguments, cwd=cwd)


def repository_slug(directory):
    """Return the owner/name the checkout in the given directory has on GitHub."""
    url = git('remote', 'get-url', 'origin', cwd=directory).removesuffix('.git')
    if ':' in url and '//' not in url:
        return url.split(':', 1)[1]
    return '/'.join(url.split('/')[-2:])


def read_addon(addon_directory):
    """Return the id and version of the add-on in the given checkout."""
    path = os.path.join(addon_directory, 'addon.xml')
    if os.path.isfile(path):
        addon = ElementTree.parse(path).getroot()
        return addon.get('id'), addon.get('version')

    # addon.xml.in is no valid XML, its attribute names contain placeholders
    for name in sorted(os.listdir(addon_directory)):
        template = os.path.join(addon_directory, name, 'addon.xml.in')
        if os.path.isfile(template):
            with open(template, 'r', encoding='utf-8') as stream:
                match = re.search(r'^\s*version="([^"]+)"', stream.read(), re.MULTILINE)
            if match:
                return name, match.group(1)
    raise SystemExit('{} holds neither addon.xml nor <id>/addon.xml.in'.format(addon_directory))


def build_release(addon_directory, tag):
    """Run the add-on's release workflow for the tag and wait until it has finished."""
    slug = repository_slug(addon_directory)
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    print('{}: building the release zips'.format(slug))
    subprocess.run(['gh', 'workflow', 'run', RELEASE_WORKFLOW, '--repo', slug,
                    '--field', 'tag={}'.format(tag)], check=True)

    # gh workflow run does not say which run it started
    run_id = None
    while run_id is None:
        time.sleep(INTERVAL)
        runs = json.loads(run('gh', 'run', 'list', '--repo', slug, '--workflow', RELEASE_WORKFLOW,
                              '--event', 'workflow_dispatch', '--json', 'databaseId,createdAt'))
        run_id = next((str(r['databaseId']) for r in runs if r['createdAt'] >= started), None)

    if subprocess.run(['gh', 'run', 'watch', run_id, '--repo', slug, '--exit-status']).returncode:
        raise SystemExit('the release workflow failed - see '
                         'https://github.com/{}/actions/runs/{}'.format(slug, run_id))


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
        entries = {entry['id']: entry for entry in json.load(stream)['addons']}
    published = list(entries)
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

    return branch, 'platforms' in entries.get(addon_id, {})


def main():
    addon_directory = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')

    addon_id, version = read_addon(addon_directory)
    tag = 'v{}'.format(version)

    branch, is_binary = check(addon_directory, addon_id, tag)

    print('{}: tagging {} as {} and pushing it'.format(addon_id, branch, tag))
    git('tag', '--annotate', tag, '--message', version, cwd=addon_directory)
    git('push', '--quiet', 'origin', branch, cwd=addon_directory)
    git('push', '--quiet', 'origin', tag, cwd=addon_directory)

    if is_binary:
        build_release(addon_directory, tag)

    slug = repository_slug(ROOT)
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
