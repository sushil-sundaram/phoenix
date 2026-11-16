#!/usr/bin/env python3
"""
COSMIC Desktop Session Restorer
Reads state snapshot from ~/.config/cosmic/session-snapshot.json,
sanitizes Chrome preferences & Local State for instant profile/tab restoration,
launches applications, and dynamically moves each window to its exact physical
screen and workspace using cos-cli with fresh index querying and verification.
"""

import subprocess
import re
import json
import os
import sys
import time
import shutil
import glob

BIN_DIR = os.path.dirname(os.path.abspath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import phoenix_profile

SNAPSHOT_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json")
BACKUP_PATH = os.path.expanduser("~/.config/cosmic/session-snapshot.json.bak")
COS_CLI = os.path.expanduser("~/phoenix/bin/cos-cli")
IGNORED_APPS = {"steam"}

def get_env():
    return phoenix_profile.get_env()

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

_INSTALLED_FLATPAKS_CACHE = None

def get_installed_flatpaks():
    global _INSTALLED_FLATPAKS_CACHE
    if _INSTALLED_FLATPAKS_CACHE is not None:
        return _INSTALLED_FLATPAKS_CACHE
    flatpaks = []
    try:
        out = subprocess.check_output(["flatpak", "list", "--app", "--columns=application"], text=True, stderr=subprocess.DEVNULL)
        flatpaks = [line.strip() for line in out.splitlines() if line.strip()]
    except Exception:
        pass
    _INSTALLED_FLATPAKS_CACHE = flatpaks
    return flatpaks

_DESKTOP_COMMANDS_CACHE = None

def get_desktop_commands():
    global _DESKTOP_COMMANDS_CACHE
    if _DESKTOP_COMMANDS_CACHE is not None:
        return _DESKTOP_COMMANDS_CACHE

    desktop_dirs = [
        os.path.expanduser("~/.local/share/applications"),
        os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
        "/var/lib/flatpak/exports/share/applications",
        "/usr/local/share/applications",
        "/usr/share/applications",
    ]
    commands = {}
    for d in desktop_dirs:
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.desktop")):
            base = os.path.basename(f)[:-8]  # strip .desktop
            wm_class = None
            exec_cmd = None
            name = None
            try:
                with open(f, "r", errors="ignore") as fp:
                    for line in fp:
                        line = line.strip()
                        if line.startswith("StartupWMClass="):
                            wm_class = line.split("=", 1)[1].strip()
                        elif line.startswith("Exec=") and not exec_cmd:
                            exec_cmd = line.split("=", 1)[1].strip()
                        elif line.startswith("Name=") and not name:
                            name = line.split("=", 1)[1].strip()
            except Exception:
                continue

            if exec_cmd:
                clean = re.sub(r"@@[a-zA-Z\s%]+@@", "", exec_cmd)
                clean = re.sub(r"%[a-zA-Z]", "", clean).strip()
                commands[base.lower()] = clean
                if wm_class:
                    commands[wm_class.lower()] = clean
                if name:
                    commands[name.lower()] = clean
                    commands[name.lower().replace(" ", "")] = clean

    _DESKTOP_COMMANDS_CACHE = commands
    return commands

def get_launch_command(app_id):
    mapping = {
        "google-chrome": "flatpak run com.google.Chrome --restore-last-session --disable-session-crashed-bubble --no-default-browser-check",
        "spotify": "flatpak run com.spotify.Client",
        "discord": "flatpak run com.discordapp.Discord",
        "com.discordapp.Discord": "flatpak run com.discordapp.Discord",
        "antigravity": "/usr/local/bin/antigravity",
        "antigravity-ide": "/usr/local/bin/antigravity-ide",
        "steam": "steam",
        "dev.warp.Warp": "/usr/bin/warp-terminal",
        "warp": "/usr/bin/warp-terminal",
        # Ghostty
        "com.mitchellh.ghostty": "ghostty",
        "ghostty": "ghostty",
        # OrcaSlicer
        "orca-slicer": "flatpak run com.orcaslicer.OrcaSlicer",
        "OrcaSlicer": "flatpak run com.orcaslicer.OrcaSlicer",
        "com.orcaslicer.OrcaSlicer": "flatpak run com.orcaslicer.OrcaSlicer",
        # BambuStudio & PrusaSlicer
        "bambu-studio": "flatpak run com.bambulab.BambuStudio",
        "BambuStudio": "flatpak run com.bambulab.BambuStudio",
        "com.bambulab.BambuStudio": "flatpak run com.bambulab.BambuStudio",
        "prusa-slicer": "flatpak run com.prusa3d.PrusaSlicer",
        "PrusaSlicer": "flatpak run com.prusa3d.PrusaSlicer",
        "com.prusa3d.PrusaSlicer": "flatpak run com.prusa3d.PrusaSlicer",
        # KiCad & FreeCAD
        "KiCad": "flatpak run org.kicad.KiCad",
        "org.kicad.KiCad": "flatpak run org.kicad.KiCad",
        "FreeCAD": "flatpak run org.freecad.FreeCAD",
        "org.freecad.FreeCAD": "flatpak run org.freecad.FreeCAD",
        # Slack, Obsidian, Signal
        "slack": "flatpak run com.slack.Slack",
        "com.slack.Slack": "flatpak run com.slack.Slack",
        "obsidian": "flatpak run md.obsidian.Obsidian",
        "md.obsidian.Obsidian": "flatpak run md.obsidian.Obsidian",
        "signal": "flatpak run org.signal.Signal",
        "org.signal.Signal": "flatpak run org.signal.Signal",
    }
    if app_id in mapping:
        return mapping[app_id]

    env = get_env()
    # 1. Direct which lookup
    if shutil.which(app_id, path=env.get("PATH")):
        return app_id

    # 2. Desktop file commands lookup
    desktop_cmds = get_desktop_commands()
    low = app_id.lower()
    if low in desktop_cmds:
        return desktop_cmds[low]
    norm = low.replace("-", "").replace("_", "").replace(" ", "")
    if norm in desktop_cmds:
        return desktop_cmds[norm]

    # 3. If app_id has dots, try last segment
    if "." in app_id:
        last_seg = app_id.split(".")[-1]
        last_low = last_seg.lower()
        if last_low in desktop_cmds:
            return desktop_cmds[last_low]
        if shutil.which(last_seg, path=env.get("PATH")):
            return last_seg

    # 4. Flatpak resolution: search installed flatpaks
    flatpaks = get_installed_flatpaks()
    for fp in flatpaks:
        fp_norm = fp.lower().replace("-", "").replace("_", "")
        last_seg = fp.split(".")[-1].lower().replace("-", "").replace("_", "")
        if norm == fp_norm or norm == last_seg or (len(norm) >= 4 and norm in fp_norm):
            return f"flatpak run {fp}"

    # 5. Fallback
    if "." in app_id:
        return f"flatpak run {app_id}"
    return app_id

APP_ALIASES = {
    "orca-slicer": {"orca-slicer", "orcaslicer", "com.orcaslicer.orcaslicer"},
    "com.orcaslicer.orcaslicer": {"orca-slicer", "orcaslicer", "com.orcaslicer.orcaslicer"},
    "ghostty": {"ghostty", "com.mitchellh.ghostty"},
    "com.mitchellh.ghostty": {"ghostty", "com.mitchellh.ghostty"},
    "kicad": {"kicad", "org.kicad.kicad"},
    "freecad": {"freecad", "org.freecad.freecad"},
    "warp": {"warp", "dev.warp.warp"},
    "dev.warp.warp": {"warp", "dev.warp.warp"},
    "slack": {"slack", "com.slack.slack"},
    "com.slack.slack": {"slack", "com.slack.slack"},
    "obsidian": {"obsidian", "md.obsidian.obsidian"},
    "md.obsidian.obsidian": {"obsidian", "md.obsidian.obsidian"},
    "discord": {"discord", "com.discordapp.discord"},
    "com.discordapp.discord": {"discord", "com.discordapp.discord"},
    "google-chrome": {"google-chrome", "com.google.chrome"},
    "com.google.chrome": {"google-chrome", "com.google.chrome"},
}

def app_ids_match(id1, id2):
    if not id1 or not id2:
        return False
    i1 = id1.lower().strip()
    i2 = id2.lower().strip()
    if i1 == i2:
        return True
    if i1 in APP_ALIASES.get(i2, set()) or i2 in APP_ALIASES.get(i1, set()):
        return True
    if i1.endswith("." + i2) or i2.endswith("." + i1):
        return True
    return False

SINGLE_INSTANCE_APPS = {
    "google-chrome", "chromium", "firefox", "brave-browser",
    "spotify", "discord", "com.discordapp.discord",
    "slack", "com.slack.slack",
    "signal", "org.signal.signal",
    "antigravity", "antigravity-ide", "steam",
    "obsidian", "md.obsidian.obsidian",
    "io.podman_desktop.podmandesktop",
}

def run_cos_cli(args):
    cmd = [COS_CLI] + args
    try:
        return subprocess.check_output(cmd, env=get_env(), text=True, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"cos-cli error ({args}): {e}", file=sys.stderr)
        return ""

def get_live_state():
    """Queries cos-cli info --json and returns dynamic output maps and live apps."""
    try:
        out = run_cos_cli(["info", "--json"])
        data = json.loads(out)
    except Exception as e:
        print(f"Error querying cos-cli info --json: {e}", file=sys.stderr)
        return {}, {}, []

    output_to_group = {}
    for wg in data.get("workspace_groups", []):
        for out_name in wg.get("outputs", []):
            output_to_group[out_name] = wg.get("index", 0)

    output_to_index = {}
    for out in data.get("outputs", []):
        output_to_index[out.get("name", "")] = out.get("index", 0)

    apps = data.get("apps", [])
    return output_to_group, output_to_index, apps

def title_similarity_score(t1, t2):
    if not t1 or not t2:
        return 0
    clean1 = re.sub(r"\s*-\s*Google Chrome.*$", "", t1, flags=re.IGNORECASE).strip().lower()
    clean2 = re.sub(r"\s*-\s*Google Chrome.*$", "", t2, flags=re.IGNORECASE).strip().lower()
    if clean1 == clean2 and clean1:
        return 100
    if clean1 in clean2 or clean2 in clean1:
        return 80
    words1 = set(re.findall(r"\w{3,}", clean1))
    words2 = set(re.findall(r"\w{3,}", clean2))
    if not words1 or not words2:
        return 0
    common = words1 & words2
    return len(common) * 15

def move_window_and_verify(track_app_id, track_title, target_output, target_ws, timeout=3.0):
    """
    Finds the window using fresh state, executes cos-cli move, and verifies that the compositor
    has moved the window to the expected physical output and workspace.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        out_to_group, out_to_idx, live_apps = get_live_state()
        candidate = None
        for a in live_apps:
            if track_title:
                if a.get("title", "") == track_title:
                    candidate = a
                    break
            elif track_app_id:
                if app_ids_match(a.get("app_id", ""), track_app_id):
                    candidate = a
                    break

        if not candidate:
            time.sleep(0.2)
            continue

        cur_out = candidate["outputs"][0]["name"] if candidate.get("outputs") else ""
        cur_ws = candidate["workspaces"][0]["index"] if candidate.get("workspaces") else -1

        if cur_out == target_output and cur_ws == target_ws:
            print(f"Verified: '{candidate.get('app_id')}' (\"{candidate.get('title')[:30]}\") at {target_output} ws {target_ws}")
            return True, candidate

        target_group = out_to_group.get(target_output)
        target_oidx = out_to_idx.get(target_output)
        if target_group is None:
            print(f"Error: Target screen '{target_output}' not found in active workspace groups.")
            return False, candidate

        idx = candidate["index"]
        move_cmd = ["move", "-i", str(idx), "-g", str(target_group), "-w", str(target_ws)]
        if target_oidx is not None:
            move_cmd.extend(["-o", str(target_oidx)])

        run_cos_cli(move_cmd)
        time.sleep(0.3)

    return False, candidate

def restore_session(profile_name=None):
    chosen_profile, reason = phoenix_profile.resolve_profile_for_restore(profile_name)
    print(f"Profile: '{chosen_profile}' ({reason})")

    paths = phoenix_profile.get_snapshot_paths(chosen_profile)
    target_file = paths["snapshot"]
    if not os.path.exists(target_file):
        target_file = paths["backup"]

    if not os.path.exists(target_file):
        if os.path.exists(SNAPSHOT_PATH):
            target_file = SNAPSHOT_PATH
        elif os.path.exists(BACKUP_PATH):
            target_file = BACKUP_PATH

    if not os.path.exists(target_file):
        print(f"No snapshot found for profile '{chosen_profile}' or fallback.", file=sys.stderr)
        return False

    with open(target_file, "r") as f:
        snapshot = json.load(f)

    saved_apps = snapshot.get("apps", [])
    if not saved_apps:
        print(f"No apps found in snapshot for profile '{chosen_profile}'.")
        return False

    print(f"Restoring {len(saved_apps)} app windows from profile '{chosen_profile}' snapshot ({snapshot.get('timestamp_str')})...")
    phoenix_profile.record_profile_action("restore", chosen_profile, reason)

    # Sanitize Chrome Local State & Preferences for auto profile/tab restoration
    sanitize_chrome_environment()

    # 1. Launch applications
    launched_apps = set()
    for app in saved_apps:
        app_id = app["app_id"]
        if app_id.lower() in IGNORED_APPS:
            continue

        # Single-instance apps launched once; multi-instance apps launched per saved window
        if app_id.lower() in SINGLE_INSTANCE_APPS and app_id in launched_apps:
            continue

        cmd = get_launch_command(app_id)
        print(f"Spawning application '{app_id}': {cmd}")
        subprocess.Popen(f"{cmd} &", shell=True, env=get_env())
        launched_apps.add(app_id)
        time.sleep(0.3)

    # 2. Poll for live windows to appear and Chrome titles to resolve (up to 35 seconds)
    print("Waiting for windows to spawn and titles to resolve...")
    expected_outputs = set(app.get("output_name") for app in saved_apps if app.get("output_name") and app.get("app_id", "").lower() not in IGNORED_APPS)
    saved_chrome_count = sum(1 for app in saved_apps if "chrome" in app.get("app_id", "").lower())
    start_time = time.time()

    while time.time() - start_time < 35:
        time.sleep(1)
        out_to_group, out_to_idx, live_apps = get_live_state()

        # Ensure all expected physical outputs are detected by the compositor
        missing_outputs = expected_outputs - set(out_to_group.keys())
        if missing_outputs:
            continue

        # Check total window count
        active_saved_count = len(saved_apps) - sum(1 for app in saved_apps if app.get("app_id", "").lower() in IGNORED_APPS)
        if len(live_apps) < active_saved_count:
            continue

        # If Chrome was saved, wait until all Chrome windows have restored titles
        if saved_chrome_count > 0:
            live_chrome = [a for a in live_apps if "chrome" in a.get("app_id", "").lower()]
            if len(live_chrome) < saved_chrome_count:
                continue
            # If any Chrome window still has empty or generic title, keep waiting for tabs to deserialize
            chrome_loading = any(
                a.get("title", "").strip() in {"", "Google Chrome", "New Tab - Google Chrome", "about:blank"}
                for a in live_chrome
            )
            if chrome_loading:
                continue

        break

    out_to_group, out_to_idx, live_apps = get_live_state()
    print(f"Found {len(live_apps)} active windows.")
    print(f"Active Output Map: {out_to_group}")

    # 3. Separate multi-window apps (like Chrome) and single-window apps for exact matching
    chrome_saved = [s for s in saved_apps if "chrome" in s.get("app_id", "").lower()]
    other_saved = [s for s in saved_apps if "chrome" not in s.get("app_id", "").lower()]

    # Match Chrome windows 1-to-1 using bipartite title scoring
    live_chrome = [l for l in live_apps if "chrome" in l.get("app_id", "").lower()]
    chrome_pairs = []
    used_live_chrome = set()

    score_matrix = []
    for si, s in enumerate(chrome_saved):
        for li, l in enumerate(live_chrome):
            score = title_similarity_score(s.get("title", ""), l.get("title", ""))
            score_matrix.append((score, si, li))

    score_matrix.sort(key=lambda x: x[0], reverse=True)
    matched_saved_chrome = set()
    for score, si, li in score_matrix:
        if si not in matched_saved_chrome and li not in used_live_chrome:
            matched_saved_chrome.add(si)
            used_live_chrome.add(li)
            chrome_pairs.append((chrome_saved[si], live_chrome[li].get("title", "")))
            print(f"Matched Chrome: '{chrome_saved[si].get('title')[:30]}' -> Live: '{live_chrome[li].get('title')[:30]}' (score {score})")

    # Fallback for any remaining Chrome windows
    for si, s in enumerate(chrome_saved):
        if si not in matched_saved_chrome:
            for li, l in enumerate(live_chrome):
                if li not in used_live_chrome:
                    matched_saved_chrome.add(si)
                    used_live_chrome.add(li)
                    chrome_pairs.append((s, l.get("title", "")))
                    print(f"Fallback Chrome match: '{s.get('title')[:30]}' -> Live: '{l.get('title')[:30]}'")
                    break

    # 4. Move Chrome windows dynamically with verification
    for saved, track_title in chrome_pairs:
        target_out = saved.get("output_name", "")
        target_ws = saved["workspace"]
        print(f"Positioning Chrome \"{track_title[:25]}\" -> Screen '{target_out}', Workspace {target_ws}")
        success, cand = move_window_and_verify(
            track_app_id="google-chrome",
            track_title=track_title,
            target_output=target_out,
            target_ws=target_ws
        )
        if not success:
            print(f"Warning: Failed to position Chrome window '{track_title[:25]}'")

    # 5. Move all other applications dynamically with verification
    # Track used live windows for apps with multiple instances
    used_live_indices = set()
    for saved in other_saved:
        app_id = saved["app_id"]
        if app_id.lower() in IGNORED_APPS:
            continue
        target_out = saved.get("output_name", "")
        target_ws = saved["workspace"]
        saved_title = saved.get("title", "")
        saved_states = saved.get("state", [])

        out_to_group, out_to_idx, live_apps = get_live_state()

        # Find matching live window that hasn't been placed yet
        candidate = None
        for live in live_apps:
            if live["index"] in used_live_indices:
                continue
            if app_ids_match(live.get("app_id", ""), app_id):
                if saved_title and (saved_title in live.get("title", "") or live.get("title", "") in saved_title):
                    candidate = live
                    break
                elif candidate is None:
                    candidate = live

        if not candidate:
            print(f"Warning: Could not find live window for '{app_id}' ({saved_title})")
            continue

        used_live_indices.add(candidate["index"])
        track_title = candidate.get("title") if candidate.get("title") else None

        print(f"Positioning '{app_id}' -> Screen '{target_out}', Workspace {target_ws}")
        success, moved_cand = move_window_and_verify(
            track_app_id=app_id,
            track_title=track_title,
            target_output=target_out,
            target_ws=target_ws
        )

        if success and moved_cand:
            # Set window state if explicitly maximized in snapshot (ignore transient 'activated' focus state)
            if "maximized" in saved_states:
                # Query fresh index
                _, _, fresh_apps = get_live_state()
                fresh = next((a for a in fresh_apps if a.get("title") == moved_cand.get("title") and app_ids_match(a.get("app_id", ""), app_id)), None)
                if fresh:
                    run_cos_cli(["state", "-i", str(fresh["index"]), "--maximize"])
            elif "minimized" in saved_states:
                _, _, fresh_apps = get_live_state()
                fresh = next((a for a in fresh_apps if a.get("title") == moved_cand.get("title") and app_ids_match(a.get("app_id", ""), app_id)), None)
                if fresh:
                    run_cos_cli(["state", "-i", str(fresh["index"]), "--minimize"])

    # 6. Activate primary workspace on primary screen at end of restoration
    run_cos_cli(["ws-activate", "--workspace", "0"])
    print("COSMIC desktop session restoration complete.")

if __name__ == "__main__":
    explicit_profile = None
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg in ("-p", "--profile") and i + 1 < len(sys.argv):
                explicit_profile = sys.argv[i + 1]
                break
            elif not arg.startswith("-") and i > 0:
                explicit_profile = arg
    restore_session(explicit_profile)
