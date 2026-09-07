# ksooo's Kodi Add-on Repository

A Kodi add-on repository for the Kodi add-ons written by ksooo. Once it is installed, the add-ons
below show up in Kodi's own add-on browser and Kodi keeps them up to date, so none of them ever has
to be installed from a zip file by hand again.

It is served from GitHub Pages at
[ksooo.github.io/repository.kodi.ksooo](https://ksooo.github.io/repository.kodi.ksooo/).

## Installation

1. Download
   [repository.kodi.ksooo-1.0.0.zip](https://ksooo.github.io/repository.kodi.ksooo/repository.kodi.ksooo/repository.kodi.ksooo-1.0.0.zip).
2. In Kodi, allow *Settings ▸ System ▸ Add-ons ▸ Unknown sources*.
3. *Add-ons ▸ Install from zip file*, and pick the downloaded file.
4. *Add-ons ▸ Install from repository ▸ ksooo's Kodi Add-ons*, and install what you want.

Kodi looks for updates on its own from then on, once a day per repository. *Add-ons ▸ Check for
updates* does it right away.

## Add-ons in this repository

| Add-on | Description |
| --- | --- |
| [Not in Library](https://github.com/ksooo/plugin.video.notinlibrary) | Finds the videos in your sources that are missing from the video library |
| [Home Assistant Dashboard](https://github.com/ksooo/script.homeassistant) | Shows your Home Assistant dashboard in Kodi |
| [FRITZ!Box Callmonitor](https://github.com/ksooo/service.kodi-fritzbox-callmonitor) | Shows information about the telephone calls routed over your FRITZ!Box |

The repository add-on itself is part of the repository as well, so it can update itself.

## Releasing a new add-on version

In the add-on's own repository, raise the version and describe the change, both in `addon.xml`:

```xml
<addon id="plugin.video.notinlibrary" version="1.1.0" ...>
  ...
  <news>v1.1.0 (2026-09-07) - What is new.</news>
```

`<news>` is what Kodi shows as the changelog in the add-on information dialog; a `changelog.txt` is
not read any more. Commit that, then release from the add-on's checkout:

```sh
git commit -am "1.1.0: What is new."
python3 ../repository.kodi.ksooo/tools/release.py
```

The script tags HEAD with the version `addon.xml` declares, pushes the branch and the tag, asks the
workflow here to rebuild, and waits until the new version really shows up in the published index -
so the command only returns once the release is live, about a minute later. It refuses to release a
dirty working tree, a detached HEAD, a branch that is behind its remote, a version that is tagged
already, or an add-on that `addons.json` does not list.

Nothing polls for new tags: the rebuild happens because the script asks for it. It can also be
started by hand from the *Actions* tab, and every push to `main` here rebuilds as well.

`addons.json` pins every add-on to `latest`, so the build resolves the highest version tag of each
add-on repository on its own; to publish something older, write that tag in place of `latest`. The
tag has to agree with `addon.xml`: a `v1.1.0` whose `addon.xml` still says 1.0.0 fails the build.
Missing the version bump would otherwise release nothing at all and stay quiet about it, as the zip
would keep its name and no client would see a new version.

### Adding a new add-on

Add an object with its `id`, clone `url` and `ref` to `addons.json`, and push. The add-on needs no
knowledge of this repository, and nothing in its own repository has to change.

## When users see the update

Kodi checks each repository once a day, so a release reaches an idle installation within 24 hours.
*Add-ons ▸ Check for updates* fetches it right away. A repository cannot shorten that interval from
its side - the header Kodi honours for it is not one GitHub Pages can send.

What the user then sees is a matter of two Kodi settings, not of this repository:

| *Settings ▸ System ▸ Add-ons ▸ Updates* | *Show notifications* | Result |
| --- | --- | --- |
| Install updates automatically (default) | off (default) | The add-on is updated silently, and the event log records it |
| Install updates automatically | on | The add-on is updated, with a notification per add-on |
| Notify, but don't install updates | – | A notification, and the update waits to be confirmed |
| Never check for updates | – | Nothing, until the user looks for updates by hand |

## How it is built

`tools/build_repo.py` writes the layout Kodi expects, and the workflow in
`.github/workflows/build.yml` runs exactly the same script:

```
addons.xml                                          the index, all add-ons in one file
addons.xml.sha256
<id>/<id>-<version>.zip                             the installable add-on
<id>/<id>-<version>.zip.sha256
<id>/<icon, screenshots as declared in addon.xml>   read from here, not from the zip
index.html                                          so the URL is useful in a browser as well
```

Everything Kodi verifies has a `.sha256` sibling, because GitHub Pages sends no content digest
header for Kodi to use instead. The archives are built with a fixed member timestamp, so a given
add-on version always builds into a byte identical zip.

Development material - `tests/`, `tools/`, `.github/`, `__pycache__/` and the like - is left out of
the archives, so the add-on repositories need no packaging tooling of their own.

Nothing is deployed when the built `addons.xml` matches the published one, so the workflow history
shows the runs that really released something, and a push that only touches the README deploys
nothing. *Run workflow* offers a `force` switch for the rare case where a deploy has to be repeated
anyway.

To build into `./public` locally, without deploying anything:

```sh
python3 tools/build_repo.py
```

## License

GPL-2.0-or-later, see [LICENSE.txt](LICENSE.txt).
