"""Show the next painting: advance the pool, then apply it as the wallpaper.

Runs at login. Everything here is local — the image was already downloaded and
composed to screen size by fetch_painting.py, so this is just a file move and
one qdbus call (~100ms, no network). If the pool is empty (offline for longer
than it held), the current painting simply stays up.

Plasma's scripting `writeConfig()` persists values to disk but does not make an
already-running wallpaper widget re-read them — only the first assignment of
wallpaperPlugin triggers a live reload. So we briefly switch to the builtin
solid-color plugin and back, which tears down and recreates the wallpaper item,
forcing it to pick up the fresh config.
"""
import subprocess
import sys
from pathlib import Path

import store

# KConfig serializes QColor as "r,g,b,a" (alpha required) — 3 components
# without alpha silently fails to parse and falls back to black.
BORDER_COLOR = "0,0,0,255"  # black letterbox/pillarbox bars

JPEG_MAGIC = b"\xff\xd8\xff"

APPLY_SCRIPT = """
var allDesktops = desktops();
for (i = 0; i < allDesktops.length; i++) {{
    d = allDesktops[i];
    d.wallpaperPlugin = "org.kde.color";
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General");
    d.writeConfig("Image", "file://{image_path}");
    d.writeConfig("FillMode", 1);
    d.writeConfig("Color", "{color}");
}}
"""


def image_of(info: dict) -> Path:
    return Path(info.get("wallpaperPath") or info.get("imagePath", ""))


def usable(path: Path) -> bool:
    """Whether Plasma will actually be able to render this file.

    Existence is not enough: an interrupted download or an unclean shutdown
    leaves a 0-byte (or header-less) file behind, and Plasma accepts such a
    path without complaint and renders a black desktop — a silent failure that
    then sticks, because the broken entry gets written to current.json. Reading
    the magic bytes is the cheapest way to reject that, and keeps this module
    stdlib-only so the login path still doesn't pay for PIL.
    """
    try:
        with path.open("rb") as fh:
            return fh.read(3) == JPEG_MAGIC
    except OSError:
        return False


def advance() -> dict | None:
    """Take the next usable painting from the pool, or keep the current one."""
    pool = store.load_pool()
    while pool:
        info = pool.pop(0)
        if usable(image_of(info)):
            store.save_pool(pool)
            store.save_current(info)
            return info
        # image was deleted or truncated behind our back — drop it, try the next
        print(f"skipping unusable image: {image_of(info)}", file=sys.stderr)
        store.save_pool(pool)

    current = store.load_current()
    return current if current and usable(image_of(current)) else None


def main() -> None:
    info = advance()
    if info is None:
        print("error: no painting available, run fetch_painting.py first", file=sys.stderr)
        sys.exit(1)

    image_path = image_of(info)
    subprocess.run(
        [
            "qdbus6",
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            APPLY_SCRIPT.format(image_path=image_path, color=BORDER_COLOR),
        ],
        check=True,
    )
    print(f"wallpaper set: {info['title']} ({image_path})")


if __name__ == "__main__":
    main()
