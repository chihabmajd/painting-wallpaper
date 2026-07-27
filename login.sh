#!/usr/bin/env bash
# Runs at login. Purely local (no network): shows the next painting from the
# pre-downloaded pool, so there's zero login latency.
set -e
cd "$(dirname "$0")"

./.venv/bin/python set_wallpaper.py
