#!/usr/bin/env python3
"""
COSMIC Desktop Session Restorer
Reads state snapshot from ~/.config/cosmic/session-snapshot.json,
sanitizes Chrome preferences & Local State for instant profile/tab restoration,
launches applications, and uses cos-cli workspace-group mapping to place windows
on exact physical screens and workspaces.
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
IGNORED_APPS = {"steam"}

def get_env():
    env = os.environ.copy()
    if "WAYLAND_DISPLAY" not in env:
        env["WAYLAND_DISPLAY"] = "wayland-1"
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    env["PATH"] = f"{os.path.expanduser('~')}/.cargo/bin:/usr/local/bin:/usr/bin:{env.get('PATH', '')}"
    return env

def sanitize_chrome_environment():
    """Disables Chrome Profile Picker and resets exit_type so tabs restore automatically."""
    local_state_paths = [
        os.path.expanduser("~/.var/app/com.google.Chrome/config/google-chrome/Local State"),
        os.path.expanduser("~/.config/google-chrome/Local State"),
    ]
    for ls_path in local_state_paths:
        if os.path.exists(ls_path):
            try:
                with open(ls_path, "r") as f:
                    data = json.load(f)
                if "profile" not in data or not isinstance(data["profile"], dict):
                    data["profile"] = {}
                data["profile"]["show_profile_picker_on_startup"] = False
                with open(ls_path, "w") as f:
                    json.dump(data, f)
                print(f"Disabled Chrome Profile Picker in {ls_path}")
            except Exception as e:
                print(f"Warning: Local State error: {e}")

    profile_dirs = [
        os.path.expanduser("~/.var/app/com.google.Chrome/config/google-chrome/Default"),
        os.path.expanduser("~/.var/app/com.google.Chrome/config/google-chrome/Profile 1"),
        os.path.expanduser("~/.config/google-chrome/Default"),
        os.path.expanduser("~/.config/google-chrome/Profile 1"),
    ]
    for pdir in profile_dirs:
        pref_file = os.path.join(pdir, "Preferences")
        if os.path.exists(pref_file):
            try:
                with open(pref_file, "r") as f:
                    data = json.load(f)
                if "profile" in data and isinstance(data["profile"], dict):
                    data["profile"]["exit_type"] = "Normal"
                if "session" not in data or not isinstance(data["session"], dict):
                    data["session"] = {}
                data["session"]["restore_on_startup"] = 1
                with open(pref_file, "w") as f:
                    json.dump(data, f)
                print(f"Sanitized Chrome preferences at {pref_file}")
            except Exception as e:
                print(f"Warning: Preferences error: {e}")

def get_launch_command(app_id):
    mapping = {
        "google-chrome": "flatpak run com.google.Chrome --restore-last-session --disable-session-crashed-bubble --no-default-browser-check",
        "spotify": "flatpak run com.spotify.Client",
        "discord": "flatpak run com.discordapp.Discord",
        "antigravity": "/usr/local/bin/antigravity",
        "antigravity-ide": "/usr/local/bin/antigravity-ide",
        "steam": "steam",
        "dev.warp.Warp": "/usr/bin/warp-terminal",
        "KiCad": "flatpak run org.kicad.KiCad",
        "org.kicad.KiCad": "flatpak run org.kicad.KiCad",
        "FreeCAD": "flatpak run org.freecad.FreeCAD",
        "org.freecad.FreeCAD": "flatpak run org.freecad.FreeCAD",
    }
    if app_id in mapping:
        return mapping[app_id]
    
    try:
        which = subprocess.run(["which", app_id], capture_output=True, text=True, env=get_env())
        if which.returncode == 0:
            return app_id
    except Exception:
        pass
    
    return f"flatpak run {app_id}"

def run_cos_cli(args):
    cmd = [COS_CLI] + args
    try:
        return subprocess.check_output(cmd, env=get_env(), text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"cos-cli error ({args}): {e}", file=sys.stderr)
        return ""

def get_live_state():
    out = run_cos_cli(["info"])
    output_to_group = {}
    output_name_to_index = {}
    in_outputs = False
    for line in out.splitlines():
        if line.startswith("Outputs:"):
            in_outputs = True
            continue
        elif line and not line.startswith("\t") and not line.startswith("["):
            in_outputs = False

        m_grp = re.search(r"\[(\d+)\]\s+Group\s+\(outputs:\s*(.*?)\)", line)
        if m_grp:
            group_id = int(m_grp.group(1))
            out_str = m_grp.group(2)
            for out_name in out_str.split(","):
                out_name = out_name.strip().strip("\"'")
                if out_name:
                    output_to_group[out_name] = group_id
                    
        if in_outputs:
            m_out = re.search(r"\[(\d+)\]\s+Output:\s+(.*)", line)
            if m_out:
                idx = int(m_out.group(1))
                name = m_out.group(2).strip()
                output_name_to_index[name] = idx

    apps = []
    pattern = re.compile(
        r"\[(\d+)\]\s+([\w\.\-]+)\s+\(title:\s*(.*?),\s*state:\s*\[(.*?)\]\s*,\s*workspaces:\s*\[(\d+)\.[\"\']?(\d+)[\"\']?\]\s*,\s*outputs:\s*\[(.*?)\]\)"
    )
    for line in out.splitlines():
        m = pattern.search(line)
        if m:
            idx, app_id, title, state, group_idx, ws_idx, output_name = m.groups()
            states = [s.strip() for s in state.split(",") if s.strip()]
            output_name = output_name.strip().strip("\"'")
            if "," in output_name:
                output_name = output_name.split(",")[0].strip().strip("\"'")
            apps.append({
                "live_index": int(idx),
                "app_id": app_id,
                "title": title,
                "state": states,
                "workspace_group": int(group_idx),
                "workspace": int(ws_idx),
                "output_name": output_name,
            })
    return output_to_group, output_name_to_index, apps

def restore_session():
    target_file = SNAPSHOT_PATH
    if not os.path.exists(target_file):
        target_file = BACKUP_PATH

    if not os.path.exists(target_file):
        print(f"No snapshot found at {SNAPSHOT_PATH} or backup.", file=sys.stderr)
        return

    with open(target_file, "r") as f:
        snapshot = json.load(f)

    saved_apps = snapshot.get("apps", [])
    if not saved_apps:
        print("No apps found in snapshot.")
        return

    print(f"Restoring {len(saved_apps)} app windows from snapshot ({snapshot.get('timestamp_str')})...")

    # Sanitize Chrome Local State & Preferences for auto profile/tab restoration
    sanitize_chrome_environment()

    # Count how many apps are saved per workspace to decide on tiling vs single window maximize
    workspace_window_counts = {}
    for app in saved_apps:
        key = (app.get("output_name", ""), app.get("workspace", 0))
        workspace_window_counts[key] = workspace_window_counts.get(key, 0) + 1

    # 1. Launch all applications (skipping ignored apps like steam)
    launched_apps = set()
    for app in saved_apps:
        app_id = app["app_id"]
        if app_id.lower() in IGNORED_APPS:
            continue
        if app_id not in launched_apps:
            cmd = get_launch_command(app_id)
            print(f"Spawning application '{app_id}': {cmd}")
            subprocess.Popen(f"{cmd} &", shell=True, env=get_env())
            launched_apps.add(app_id)

    # 2. Poll for live windows to appear and Chrome titles to resolve (up to 40 seconds)
    print("Waiting for windows to spawn and titles to resolve...")
    live_output_map, live_output_idx_map, live_windows = {}, {}, []
    expected_outputs = set(app.get("output_name") for app in saved_apps if app.get("output_name") and app.get("app_id", "").lower() not in IGNORED_APPS)
    start_time = time.time()
    
    while time.time() - start_time < 40:
        time.sleep(1)
        live_output_map, live_output_idx_map, live_windows = get_live_state()
        
        # Ensure that cos-cli has discovered the physical outputs for the workspace groups.
        missing_outputs = expected_outputs - set(live_output_map.keys())
        if missing_outputs:
            continue
            
        if len(live_windows) < len(saved_apps) - sum(1 for app in saved_apps if app.get("app_id", "").lower() in IGNORED_APPS):
            continue
            
        # Check if Chrome windows are still loading (title is exactly "Google Chrome")
        chrome_loading = False
        for live in live_windows:
            if live["app_id"] == "google-chrome" and live["title"].strip() == "Google Chrome":
                chrome_loading = True
                break
                
        if not chrome_loading:
            break

    print(f"Found {len(live_windows)} active windows.")
    print(f"Accurate Output Map: {live_output_map}")

    # Sort saved_apps by workspace_group and workspace to ensure stable tiling order during sequential moves
    saved_apps.sort(key=lambda x: (x.get("workspace_group", 0), x.get("workspace", 0)))

    # 3. Match each saved app to a live window and position it precisely using workspace-group
    matched_live_indices = set()

    for saved in saved_apps:
        app_id = saved["app_id"]
        if app_id.lower() in IGNORED_APPS:
            continue
        saved_output_name = saved.get("output_name", "")
        saved_ws = saved["workspace"]
        saved_title = saved.get("title", "")
        saved_states = saved.get("state", [])

        # Look up live group index for the target physical output display
        target_group = live_output_map.get(saved_output_name, saved.get("workspace_group", 0))
        ws_count = workspace_window_counts.get((saved_output_name, saved_ws), 1)

        candidate = None
        for live in live_windows:
            if live["live_index"] in matched_live_indices:
                continue
            if live["app_id"].lower() == app_id.lower():
                if saved_title and (saved_title in live["title"] or live["title"] in saved_title):
                    candidate = live
                    break
                elif candidate is None:
                    candidate = live

        if candidate:
            matched_live_indices.add(candidate["live_index"])
            idx = candidate["live_index"]
            print(f"Moving '{app_id}' [Window #{idx}] -> Screen '{saved_output_name}' (Group {target_group}), Workspace {saved_ws}")
            
            # Pre-activate target workspace to ensure workspace node exists in COSMIC compositor
            run_cos_cli([
                "ws-activate",
                "--workspace-group", str(target_group),
                "--workspace", str(saved_ws)
            ])
            time.sleep(0.2)

            target_output_idx = live_output_idx_map.get(saved_output_name)
            
            move_cmd = [
                "move",
                "--index", str(idx),
                "--workspace-group", str(target_group),
                "--workspace", str(saved_ws)
            ]
            
            if target_output_idx is not None:
                move_cmd.extend(["--output-index", str(target_output_idx)])
                
            # Move window to target workspace
            run_cos_cli(move_cmd)
            time.sleep(0.2)

            if ws_count > 1:
                run_cos_cli(["state", "--index", str(idx), "--unmaximize"])
            elif "maximized" in saved_states or "activated" in saved_states:
                run_cos_cli(["state", "--index", str(idx), "--maximize"])
            elif "minimized" in saved_states:
                run_cos_cli(["state", "--index", str(idx), "--minimize"])
        else:
            print(f"Warning: Could not find live window match for '{app_id}' ({saved_title})")

    # Activate primary workspace
    run_cos_cli(["ws-activate", "--workspace", "0"])
    print("COSMIC desktop session restoration complete.")

if __name__ == "__main__":
    restore_session()
