#!/usr/bin/env python3
"""
COSMIC Desktop Session Saver
Captures active applications, window titles, workspace groups, workspaces,
outputs, and window states using cos-cli and saves to profile-specific JSON snapshot.
"""

import subprocess
import json
import os
import sys
import time

BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import phoenix_profile

COS_CLI = os.path.expanduser("~/phoenix/bin/cos-cli")
IGNORED_APPS = {"steam"}

def get_env():
    return phoenix_profile.get_env()

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

def save_session(profile_name=None):
    target_profile = phoenix_profile.resolve_profile_for_save(profile_name)
    paths = phoenix_profile.get_snapshot_paths(target_profile)
    snapshot_path = paths["snapshot"]
    backup_path = paths["backup"]

    snapshot = capture_session()
    if snapshot is None:
        return False

    snapshot["profile"] = target_profile

    # Only overwrite if valid apps were captured
    if snapshot["apps"]:
        if os.path.exists(snapshot_path):
            try:
                os.replace(snapshot_path, backup_path)
            except Exception:
                pass
        with open(snapshot_path, "w") as f:
            json.dump(snapshot, f, indent=2)

        # Keep legacy snapshot in sync for backwards compatibility
        phoenix_profile.sync_legacy_snapshot(snapshot_path)
        phoenix_profile.record_profile_action("save", target_profile, f"saved {len(snapshot['apps'])} windows")
        print(f"[{snapshot['timestamp_str']}] Saved {len(snapshot['apps'])} app windows to profile '{target_profile}' ({snapshot_path})")
        return True
    else:
        print("No active app windows captured. Skipping overwrite.")
        return False

def main():
    explicit_profile = None
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg in ("-p", "--profile") and i + 1 < len(sys.argv):
                explicit_profile = sys.argv[i + 1]
                break
            elif not arg.startswith("-") and i > 0:
                explicit_profile = arg

    success = save_session(explicit_profile)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
