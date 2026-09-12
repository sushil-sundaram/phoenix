#!/usr/bin/env python3
"""
COSMIC Desktop Session Saver
Captures active applications, window titles, workspace groups, workspaces,
outputs, and window states using cos-cli and saves to JSON snapshot.
"""

import subprocess
import re
import json
import os
import sys
import time

SNAPSHOT_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json")
BACKUP_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json.bak")
COS_CLI = os.path.expanduser("~/phoenix/bin/cos-cli")

def get_env():
    env = os.environ.copy()
    if "WAYLAND_DISPLAY" not in env:
        env["WAYLAND_DISPLAY"] = "wayland-1"
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["PATH"] = f"{os.path.expanduser('~')}/.cargo/bin:/usr/local/bin:/usr/bin:{env.get('PATH', '')}"
    return env

IGNORED_APPS = {"steam"}

def capture_session():
    if not os.path.exists(COS_CLI):
        print(f"Error: cos-cli not found at {COS_CLI}", file=sys.stderr)
        return None

    try:
        out = subprocess.check_output([COS_CLI, "info"], env=get_env(), text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Error executing cos-cli info: {e}", file=sys.stderr)
        return None

    output_to_group = {}
    for line in out.splitlines():
        m_grp = re.search(r"\[(\d+)\]\s+Group\s+\(outputs:\s*(.*?)\)", line)
        if m_grp:
            group_id = int(m_grp.group(1))
            out_str = m_grp.group(2)
            for out_name in out_str.split(","):
                out_name = out_name.strip().strip("\"'")
                if out_name:
                    output_to_group[out_name] = group_id

    apps = []
    pattern = re.compile(
        r"\[(\d+)\]\s+([\w\.\-]*)\s*\(title:\s*(.*?),\s*state:\s*\[(.*?)\]\s*,\s*workspaces:\s*\[(\d+)\.[\"\']?(\d+)[\"\']?\]\s*,\s*outputs:\s*\[(.*?)\]\)"
    )

    for line in out.splitlines():
        m = pattern.search(line)
        if m:
            idx, app_id, title, state, group_idx, ws_idx, output_name = m.groups()
            app_id = app_id.strip()
            title = title.strip()
            if not app_id:
                app_id = title.split()[0] if title else "unknown"
            
            if app_id.lower() in IGNORED_APPS:
                continue
            states = [s.strip() for s in state.split(",") if s.strip()]
            output_name = output_name.strip().strip("\"'")
            if "," in output_name:
                output_name = output_name.split(",")[0].strip().strip("\"'")
            apps.append({
                "app_id": app_id,
                "title": title,
                "state": states,
                "workspace_group": int(group_idx),
                "workspace": int(ws_idx),
                "output_name": output_name,
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

    # If we have valid apps, update snapshot and backup
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
