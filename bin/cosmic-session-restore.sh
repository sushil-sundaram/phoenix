#!/usr/bin/env bash
# COSMIC Desktop Session Restoration Wrapper
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-1}"
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

python3 "$HOME/phoenix/bin/cosmic-session-restorer.py" > /tmp/cosmic-session-restore.log 2>&1

