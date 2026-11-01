#!/usr/bin/env bash
# COSMIC Desktop Session Restoration Wrapper
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if [ -z "$WAYLAND_DISPLAY" ] || [ ! -e "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    if [ -e "$XDG_RUNTIME_DIR/wayland-1" ]; then
        export WAYLAND_DISPLAY="wayland-1"
    elif [ -e "$XDG_RUNTIME_DIR/wayland-0" ]; then
        export WAYLAND_DISPLAY="wayland-0"
    else
        export WAYLAND_DISPLAY="wayland-1"
    fi
fi

export PATH="$HOME/.cargo/bin:$HOME/.pixi/bin:$HOME/.local/bin:/usr/local/bin:$PATH"

python3 "$HOME/phoenix/bin/cosmic-session-restorer.py" > /tmp/cosmic-session-restore.log 2>&1
