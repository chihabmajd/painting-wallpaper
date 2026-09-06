"""Compose the painting onto a screen-sized black canvas, clear of the panels."""
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QGuiApplication

import store

VERTICAL_NUDGE_MM = 1

# QScreen.availableGeometry() misses the panel under Wayland/KDE, so panel
# geometry is queried from Plasma's own scripting API instead.
PANEL_QUERY_SCRIPT = """
var result = [];
var p = panels();
for (i = 0; i < p.length; i++) {
    result.push({location: p[i].location, height: p[i].height, width: p[i].width});
}
print(JSON.stringify(result));
"""


def query_panels() -> list[dict]:
    proc = subprocess.run(
        [
            "qdbus6",
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            PANEL_QUERY_SCRIPT,
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    return json.loads(proc.stdout.strip() or "[]")


def safe_area(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    """Returns (x, y, width, height) of the area clear of all panels."""
    x, y, w, h = 0, 0, screen_width, screen_height
    try:
        panels = query_panels()
    except (subprocess.SubprocessError, json.JSONDecodeError, ValueError):
        panels = []

    for panel in panels:
        loc = panel.get("location")
        if loc == "bottom":
            h -= panel["height"]
        elif loc == "top":
            y += panel["height"]
            h -= panel["height"]
        elif loc == "left":
            x += panel["width"]
            w -= panel["width"]
        elif loc == "right":
            w -= panel["width"]
    return x, y, w, h


def compose(raw_path: Path, object_id: int) -> Path:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    screen = QGuiApplication.primaryScreen()
    full = screen.geometry()

    area_x, area_y, area_w, area_h = safe_area(full.width(), full.height())

    painting = Image.open(raw_path).convert("RGB")

    scale = min(area_w / painting.width, area_h / painting.height)
    new_size = (max(1, int(painting.width * scale)), max(1, int(painting.height * scale)))
    painting = painting.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGB", (full.width(), full.height()), "black")

    px_per_mm = screen.physicalDotsPerInchY() / 25.4
    nudge_px = round(VERTICAL_NUDGE_MM * px_per_mm)

    offset_x = area_x + (area_w - painting.width) // 2
    offset_y = area_y + (area_h - painting.height) // 2 - nudge_px
    offset_y = max(area_y, offset_y)
    canvas.paste(painting, (offset_x, offset_y))

    # Atomic write, as in fetch_painting: a truncated file shows a black desktop.
    out_path = store.MEDIA_DIR / f"{object_id}_wallpaper.jpg"
    tmp_path = out_path.with_name(out_path.name + ".part")
    with tmp_path.open("wb") as fh:
        canvas.save(fh, format="JPEG", quality=92)
        fh.flush()
        os.fsync(fh.fileno())
    tmp_path.replace(out_path)
    return out_path


if __name__ == "__main__":
    result = compose(Path(sys.argv[1]), sys.argv[2])
    print(result)
