#!/usr/bin/env bash
# COSMIC Desktop Session Restoration Wrapper (run by XDG autostart at login)
set -u
umask 077

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if [ -z "${WAYLAND_DISPLAY:-}" ] || [ ! -e "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ]; then
    if [ -e "$XDG_RUNTIME_DIR/wayland-1" ]; then
        export WAYLAND_DISPLAY="wayland-1"
    elif [ -e "$XDG_RUNTIME_DIR/wayland-0" ]; then
        export WAYLAND_DISPLAY="wayland-0"
    else
        export WAYLAND_DISPLAY="wayland-1"
    fi
fi

export PATH="${PATH:-/usr/bin:/bin}:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$HOME/.pixi/bin"

# Resolve the real location of this script so the repo can live anywhere.
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"

# Give NetworkManager a moment to associate so Wi-Fi based detection works at boot.
if command -v nm-online >/dev/null 2>&1; then
    nm-online -q -t 15 || true
fi

# Private, per-user log (not a predictable, world-readable file in /tmp).
LOG_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/phoenix"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/restore.log"
[ -f "$LOG_FILE" ] && mv -f "$LOG_FILE" "$LOG_FILE.1"

exec python3 "$SCRIPT_DIR/cosmic-session-restorer.py" "$@" >"$LOG_FILE" 2>&1
