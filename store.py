"""On-disk state shared by the fetch, wallpaper, and popup steps."""
import json
from pathlib import Path

# Stdlib-only so the login path can import this without pulling in requests/PIL.
MEDIA_DIR = Path(__file__).parent / "media" / "metwallpapers"
POOL_FILE = MEDIA_DIR / "pool.json"
CURRENT_FILE = MEDIA_DIR / "current.json"
SEEN_FILE = MEDIA_DIR / "seen_ids.json"

# Kept downloaded ahead of time so every login shows instantly and a few offline days still work.
POOL_SIZE = 3


def _read(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except ValueError:
        return default


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def load_pool() -> list[dict]:
    return _read(POOL_FILE, [])


def save_pool(pool: list[dict]) -> None:
    _write(POOL_FILE, pool)


def load_current() -> dict | None:
    return _read(CURRENT_FILE, None)


def save_current(info: dict) -> None:
    _write(CURRENT_FILE, info)


def load_seen() -> set[int]:
    return set(_read(SEEN_FILE, []))


def save_seen(seen: set[int]) -> None:
    _write(SEEN_FILE, sorted(seen))
