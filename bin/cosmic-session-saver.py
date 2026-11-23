#!/usr/bin/env python3
"""
COSMIC Desktop Session Saver
Captures active applications, window titles, workspace groups, workspaces,
outputs, and window states using cos-cli and saves to profile-specific JSON snapshot.

Exit codes: 0 = saved or intentionally skipped (no windows / restore in progress),
            1 = error, 2 = invalid arguments.
"""

import argparse
import shutil
import subprocess
import json
import os
import re
import sys
import time

BIN_DIR = os.path.dirname(os.path.realpath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import phoenix_profile

COS_CLI = phoenix_profile.COS_CLI

SNAPSHOT_SCHEMA_VERSION = 1
MAX_WORKSPACE_INDEX = 31
DROP_GRACE_SECONDS = 600
# Same identifier rule the restorer enforces; anything else is never saved.
APP_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")


def get_env():
    return phoenix_profile.get_env()


def _as_int(v, default=0):
    return v if isinstance(v, int) and not isinstance(v, bool) and v >= 0 else default


def capture_session():
    if not os.path.exists(COS_CLI):
        print(f"Error: cos-cli not found at {COS_CLI}", file=sys.stderr)
        return None

    try:
        out = subprocess.check_output(
            [COS_CLI, "info", "--json"], env=get_env(), text=True,
            stderr=subprocess.DEVNULL, timeout=phoenix_profile.CMD_TIMEOUT,
        )
        data = json.loads(out)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        print(f"Error executing cos-cli info --json: {e}", file=sys.stderr)
        return None

    output_to_group = {}
    for wg in data.get("workspace_groups", []):
        for out_name in wg.get("outputs", []):
            output_to_group[out_name] = wg.get("index", 0)

    apps = []
    for app in data.get("apps", []):
        app_id = (app.get("app_id") or "").strip()
        title = (app.get("title") or "").strip()
        # Windows without an app_id cannot be relaunched safely; never guess a
        # command from the (attacker-controllable) window title.
        if not app_id:
            continue

        if not APP_ID_RE.fullmatch(app_id) or phoenix_profile.is_ignored_app(app_id, title):
            continue

        ws_list = app.get("workspaces") or []
        ws_group = _as_int(ws_list[0].get("group_index", 0)) if ws_list else 0
        ws_idx = min(_as_int(ws_list[0].get("index", 0)), MAX_WORKSPACE_INDEX) if ws_list else 0

        out_list = app.get("outputs") or []
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
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "timestamp": time.time(),
        "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "output_to_group": output_to_group,
        "apps": apps
    }
    return snapshot


def save_session(profile_name=None, wait=False, unattended=None):
    """Returns True on save, None when intentionally skipped, False on error."""
    if unattended is None:
        unattended = profile_name is None
    target_profile = phoenix_profile.resolve_profile_for_save(profile_name)
    paths = phoenix_profile.get_snapshot_paths(target_profile, create=True)
    snapshot_path = paths["snapshot"]
    backup_path = paths["backup"]

    # Never save while a restore is in flight: the layout is half-built and would
    # overwrite the good snapshot (and then rotate it out of .bak).
    with phoenix_profile.file_lock(phoenix_profile.SESSION_LOCK, blocking=wait, timeout=60) as got:
        if not got:
            print("Restore or another save in progress; skipping save.")
            return None

        snapshot = capture_session()
        if snapshot is None:
            return False

        snapshot["profile"] = target_profile

        # Only overwrite if valid apps were captured
        if not snapshot["apps"]:
            print("No active app windows captured. Skipping overwrite.")
            return None

        prev_count = None
        prev_ok = False
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r") as f:
                    prev = json.load(f)
                prev_count = len(prev.get("apps", []))
                prev_ok = True
            except (OSError, ValueError, AttributeError, TypeError):
                pass

        # Unattended saves (timer / shutdown) refuse to replace a large layout with
        # a much smaller one until the drop has persisted for DROP_GRACE_SECONDS.
        # This protects the good snapshot from login catch-up ticks, half-finished
        # restores and the shutdown save racing app teardown.
        drop_marker = os.path.join(paths["dir"], ".window-drop-since")
        new_count = len(snapshot["apps"])
        sharp_drop = prev_count is not None and prev_count >= 4 and new_count * 2 < prev_count
        if unattended and sharp_drop:
            try:
                with open(drop_marker, "r") as f:
                    since = float(f.read().strip())
            except (OSError, ValueError):
                since = None
            if since is None:
                with open(drop_marker, "w") as f:
                    f.write(str(time.time()))
            if since is None or time.time() - since < DROP_GRACE_SECONDS:
                print(f"Window count dropped {prev_count} -> {new_count}; keeping existing snapshot for now "
                      f"(will save if it persists {DROP_GRACE_SECONDS // 60} min, or run 'phoenix save').")
                return None
        try:
            os.unlink(drop_marker)
        except FileNotFoundError:
            pass

        # Keep the previous good snapshot as .bak (copy, so a crash between the
        # two steps never leaves us without a primary snapshot). Never rotate a
        # corrupt primary over a good backup.
        if prev_ok:
            shutil.copy2(snapshot_path, backup_path)
        phoenix_profile.atomic_write_json(snapshot_path, snapshot)

    phoenix_profile.record_profile_action("save", target_profile, f"saved {len(snapshot['apps'])} windows")
    print(f"[{snapshot['timestamp_str']}] Saved {len(snapshot['apps'])} app windows to profile '{target_profile}' ({snapshot_path})")
    return True


def main():
    parser = argparse.ArgumentParser(description="Save the current COSMIC window layout to a Phoenix profile.")
    parser.add_argument("-p", "--profile", dest="profile_opt", default=None, help="Profile to save into")
    parser.add_argument("profile", nargs="?", default=None, help="Profile to save into (positional form)")
    parser.add_argument("--wait", action="store_true", help="Wait for a running restore to finish instead of skipping")
    parser.add_argument("--force", action="store_true", help="Save even if the window count dropped sharply")
    args = parser.parse_args()

    try:
        profile = args.profile_opt or args.profile
        result = save_session(profile, wait=args.wait, unattended=(profile is None and not args.force))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    sys.exit(1 if result is False else 0)


if __name__ == "__main__":
    main()
