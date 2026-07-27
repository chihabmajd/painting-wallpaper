#!/usr/bin/env bash
# Runs in the background after login and on a daily timer. Does the network
# work (Met API + Wikipedia + image download) so login never has to wait on it.
set -e
cd "$(dirname "$0")"

./.venv/bin/python fetch_painting.py
