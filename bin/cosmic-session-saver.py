#!/usr/bin/env python3
"""
COSMIC Desktop Session Saver
Captures active applications, window titles, workspace groups, workspaces,
outputs, and window states using cos-cli and saves to JSON snapshot.
"""

import subprocess
import json
import os
import sys
import time

SNAPSHOT_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json")
BACKUP_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json.bak")
COS_CLI = os.path.expanduser("~/phoenix/bin/cos-cli")
IGNORED_APPS = {"steam"}

def get_env():
    env = os.environ.copy()
    uid = os.getuid()
    runtime_dir = env.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    env["XDG_RUNTIME_DIR"] = runtime_dir

    if "WAYLAND_DISPLAY" not in env or not os.path.exists(os.path.join(runtime_dir, env.get("WAYLAND_DISPLAY", ""))):
        for candidate in ["wayland-1", "wayland-0"]:
            if os.path.exists(os.path.join(runtime_dir, candidate)):
                env["WAYLAND_DISPLAY"] = candidate
                break
        else:
            env["WAYLAND_DISPLAY"] = "wayland-1"

    home = os.path.expanduser("~")
    extra_paths = f"{home}/.cargo/bin:{home}/.pixi/bin:{home}/.local/bin:/usr/local/bin:/usr/bin"
    env["PATH"] = f"{extra_paths}:{env.get('PATH', '')}"
    return env

def capture_session():
    if not os.path.exists(COS_CLI):
        print(f"Error: cos-cli not found at {COS_CLI}", file=sys.stderr)
        return None

    try:
        out = subprocess.check_output([COS_CLI, "info", "--json"], env=get_env(), text=True, stderr=subprocess.DEVNULL)
        data = json.loads(out)
    except Exception as e:
        print(f"Error executing cos-cli info --json: {e}", file=sys.stderr)
        return None

    output_to_group = {}
    for wg in data.get("workspace_groups", []):
        for out_name in wg.get("outputs", []):
            output_to_group[out_name] = wg.get("index", 0)

    apps = []
    for app in data.get("apps", []):
        app_id = app.get("app_id", "").strip()
        title = app.get("title", "").strip()
        if not app_id:
            app_id = title.split()[0] if title else "unknown"

        if app_id.lower() in IGNORED_APPS:
            continue

        ws_list = app.get("workspaces", [])
        ws_group = ws_list[0].get("group_index", 0) if ws_list else 0
        ws_idx = ws_list[0].get("index", 0) if ws_list else 0

        out_list = app.get("outputs", [])
        out_name = out_list[0].get("name", "") if out_list else ""

        apps.append({
            "app_id": app_id,
            "title": title,
            "state": app.get("state", []),
            "workspace_group": ws_group,
            "workspace": ws_idx,
            "output_name": out_name,
        })

    snapshot = {
        "timestamp": time.time(),
        "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_to_group": output_to_group,
        "apps": apps
    }
    return snapshot

def main():
    os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
    snapshot = capture_session()
    if snapshot is None:
        sys.exit(1)

    # Only overwrite if valid apps were captured
    if snapshot["apps"]:
        if os.path.exists(SNAPSHOT_PATH):
            try:
                os.replace(SNAPSHOT_PATH, BACKUP_PATH)
            except Exception:
                pass
        with open(SNAPSHOT_PATH, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"[{snapshot['timestamp_str']}] Saved {len(snapshot['apps'])} app windows to {SNAPSHOT_PATH}")
    else:
        print(f"No active app windows captured. Skipping overwrite.")

if __name__ == "__main__":
    main()
