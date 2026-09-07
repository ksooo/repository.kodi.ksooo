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

Every add-on lives in its own repository and is published from a git tag that `addons.json` pins.
A release therefore touches two repositories.

### 1. In the add-on's own repository

Raise the version and describe the change, both in `addon.xml`:

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

### 2. In this repository

Point the add-on's `ref` in `addons.json` at the new tag, and push:

```sh
git commit -am "plugin.video.notinlibrary 1.1.0"
git push
```

That push runs the *Build repository* workflow: it checks out the pinned tag of every add-on, packs
each one, rebuilds `addons.xml` and deploys the result to GitHub Pages. It takes about a minute,
and the *Actions* tab shows whether it worked.

Nothing else is needed. The index has changed, so the next update check on an installed Kodi offers
the new version.

### Two things that go wrong silently

* **The version in `addon.xml` has to be raised.** Without it the zip keeps its name, `addons.xml`
  stays as it was, and no client notices anything.
* **Push the tag before pushing `addons.json`.** Otherwise the checkout in the workflow fails. That
  is loud rather than silent - the run turns red and nothing is deployed - but the release is not
  out until the tag is there.

### Adding a new add-on

Add an object with its `id`, clone `url` and `ref` to `addons.json` and push. The add-on needs no
knowledge of this repository, and nothing in its own repository has to change.

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

To build into `./public` locally, without deploying anything:

```sh
python3 tools/build_repo.py
```

`tools/make_icon.py` draws the repository add-on icon and writes it to
`src/repository.kodi.ksooo/icon.png`.

## License

GPL-2.0-or-later, see [LICENSE.txt](LICENSE.txt).
