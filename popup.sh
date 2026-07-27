#!/usr/bin/env bash
# Runs as its own long-lived systemd unit (not backgrounded inside login.sh)
# so systemd's cgroup cleanup doesn't kill it the instant login.sh exits.
cd "$(dirname "$0")"

exec ./.venv/bin/python popup.py
