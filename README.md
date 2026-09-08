# painting-wallpaper

Sets the KDE Plasma wallpaper to a painting from the Metropolitan Museum collection, with
a popup showing what it is. Paintings are fetched ahead of time, so login never waits on
the network.

The aim is learning rather than decoration: each painting arrives with its title, artist,
date and a short description, so a login is a chance to meet a work I would not have
looked up on my own.

Linux, KDE Plasma. Uses `qdbus6` to apply the wallpaper.

## How it works

Three entry points, meant to be wired to login and a daily timer:

| Script | When | What it does |
|---|---|---|
| `fetch.sh` → `fetch_painting.py` | background after login, and daily | Tops the pool up to three paintings: picks an unseen Met highlight, downloads the image, pulls a description from Wikidata and Wikipedia, and pre-composes it to screen size |
| `login.sh` → `set_wallpaper.py` | at login | Advances the pool and applies the next painting. Purely local, no network |
| `popup.sh` → `popup.py` | after login | Shows a card with the title, artist, date and description |

Composition happens at fetch time rather than at display time, so applying a wallpaper
costs nothing. Images are letterboxed to the screen with black bars and positioned inside
the area left free by Plasma panels, which are queried over D-Bus.

State lives in `media/metwallpapers/`: `pool.json` for what is ready, `current.json` for
what is showing, `seen_ids.json` so a painting is not repeated. All of it is regenerable
and none of it is committed.

## Setup

```bash
python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./fetch.sh        # fills the pool, takes a minute
./login.sh        # applies the first painting
```

The Met Collection API needs no key.

Running it automatically is left to you: no unit files are shipped. What is needed is a
service running `login.sh` at session start, a second one running `popup.sh`, and a timer
firing `fetch.sh` daily. One constraint is worth knowing before writing them: `popup.sh`
must be its own long-lived unit rather than backgrounded from `login.sh`, otherwise
systemd's cgroup cleanup kills it as soon as `login.sh` exits.

## Limitations

- KDE Plasma only. The wallpaper is applied through the Plasma D-Bus scripting interface.
- Restricted to Met objects flagged as highlights with a public-domain image.
- Descriptions depend on the object having a Wikidata link; otherwise a short description
  is built from the Met metadata.
