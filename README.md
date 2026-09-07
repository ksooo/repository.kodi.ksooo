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

Everything after the tag happens on its own. In the add-on's own repository, raise the version and
describe the change, both in `addon.xml`:

```xml
<addon id="plugin.video.notinlibrary" version="1.1.0" ...>
  ...
  <news>v1.1.0 (2026-09-07) - What is new.</news>
```

`<news>` is what Kodi shows as the changelog in the add-on information dialog; a `changelog.txt` is
not read any more. Then commit, tag and push both:

```sh
git commit -am "1.1.0: What is new."
git tag -a v1.1.0 -m "1.1.0"
git push && git push origin v1.1.0
```

That is the whole release. `addons.json` pins every add-on to `latest`, so the build resolves the
highest version tag of each add-on repository on its own. The workflow here runs hourly, picks up
the new tag, packs it and deploys. To skip the wait, run *Build repository* from the *Actions* tab.

The tag has to agree with `addon.xml`: a `v1.1.0` whose `addon.xml` still says 1.0.0 fails the
build. Missing the version bump would otherwise release nothing at all and stay quiet about it, as
the zip would keep its name and no client would see a new version.

To publish something other than the newest tag, write that tag into `addons.json` in place of
`latest`.

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
shows the runs that really released something. *Run workflow* offers a `force` switch for the rare
case where a deploy has to be repeated anyway.

The hourly schedule is what picks up a new tag. GitHub disables scheduled workflows in repositories
that see no pushes for 60 days, so after two quiet months the schedule has to be switched back on
in the *Actions* tab - or the first release after such a pause started by hand.

To build into `./public` locally, without deploying anything:

```sh
python3 tools/build_repo.py
```

## License

GPL-2.0-or-later, see [LICENSE.txt](LICENSE.txt).
