"""Advance the pool and apply the next painting as the wallpaper via qdbus."""
import subprocess
import sys
from pathlib import Path

import store

# KConfig wants QColor as "r,g,b,a"; without alpha, parsing silently fails.
BORDER_COLOR = "0,0,0,255"  # black letterbox/pillarbox bars

JPEG_MAGIC = b"\xff\xd8\xff"

# writeConfig() does not make a running widget re-read its config, so the
# plugin is toggled off and back on to force a reload.
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
    """Reject incomplete files, which Plasma renders as a black desktop.

A magic-byte check keeps this module stdlib-only.
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
        # image was deleted or truncated behind our back; drop it and try the next
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
