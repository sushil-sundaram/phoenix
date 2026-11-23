#!/usr/bin/env python3
"""
COSMIC Desktop Session Restorer
Reads the active/auto-detected profile's snapshot from
~/.config/cosmic/profiles/<profile>/session-snapshot.json, sanitizes Chrome
preferences for tab restoration, launches applications that are not already
running, and moves each window to its saved physical screen and workspace using
cos-cli with fresh state querying and verification.

Exit codes: 0 = restored, 1 = nothing to restore / error, 2 = invalid arguments,
            3 = another restore is already running.
"""

import argparse
import collections
import glob
import itertools
import json
import os
import re
import shlex
import subprocess
import sys
import time

BIN_DIR = os.path.dirname(os.path.realpath(__file__))
if BIN_DIR not in sys.path:
    sys.path.insert(0, BIN_DIR)

import phoenix_profile

COS_CLI = phoenix_profile.COS_CLI
CMD_TIMEOUT = phoenix_profile.CMD_TIMEOUT

# app_ids come from Wayland clients and are attacker-controllable: only ever
# treat them as identifiers, never as commands.
APP_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
MAX_WORKSPACE_INDEX = 31
WAIT_FOR_WINDOWS_SECONDS = 35
WAIT_FOR_OUTPUTS_SECONDS = 10
CHROME_LOADING_TITLES = {"", "google chrome", "new tab - google chrome", "about:blank"}


def get_env():
    return phoenix_profile.get_env()


def _s(v):
    """Coerce possibly-null JSON values to str."""
    return v if isinstance(v, str) else ""


def _ws_index(v):
    if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_WORKSPACE_INDEX:
        return v
    return 0


# ---------------------------------------------------------------------------
# Chrome preference sanitizing
# ---------------------------------------------------------------------------

CHROME_CONFIG_DIRS = [
    os.path.expanduser("~/.var/app/com.google.Chrome/config/google-chrome"),
    os.path.expanduser("~/.config/google-chrome"),
]


def _chrome_running(cfg_dir):
    return os.path.lexists(os.path.join(cfg_dir, "SingletonLock"))


def _rewrite_json(path, mutate):
    with open(path, "r") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("unexpected JSON structure")
    mutate(data)
    phoenix_profile.atomic_write_json(path, data, indent=None)


def sanitize_chrome_environment():
    """Disables Chrome Profile Picker and resets exit_type so tabs restore automatically.

    Skipped while Chrome is running (it would overwrite or race our edits), and
    files are rewritten atomically so a crash can never truncate Local State
    (which holds the os_crypt key for saved passwords/cookies).
    """
    for cfg_dir in CHROME_CONFIG_DIRS:
        if not os.path.isdir(cfg_dir):
            continue
        if _chrome_running(cfg_dir):
            print(f"Chrome is running ({cfg_dir}); leaving its preferences untouched.")
            continue

        ls_path = os.path.join(cfg_dir, "Local State")
        profile_names = ["Default"]
        if os.path.exists(ls_path):
            def fix_local_state(data):
                if not isinstance(data.get("profile"), dict):
                    data["profile"] = {}
                data["profile"]["show_profile_picker_on_startup"] = False
                cache = data["profile"].get("info_cache")
                if isinstance(cache, dict):
                    profile_names[:] = [n for n in cache if isinstance(n, str) and "/" not in n] or ["Default"]
            try:
                _rewrite_json(ls_path, fix_local_state)
                print(f"Disabled Chrome Profile Picker in {ls_path}")
            except (OSError, ValueError) as e:
                print(f"Warning: Local State error: {e}")

        for pname in profile_names:
            pref_file = os.path.join(cfg_dir, pname, "Preferences")
            if not os.path.exists(pref_file):
                continue

            def fix_prefs(data):
                if isinstance(data.get("profile"), dict):
                    data["profile"]["exit_type"] = "Normal"
                if not isinstance(data.get("session"), dict):
                    data["session"] = {}
                data["session"]["restore_on_startup"] = 1
            try:
                _rewrite_json(pref_file, fix_prefs)
                print(f"Sanitized Chrome preferences at {pref_file}")
            except (OSError, ValueError) as e:
                print(f"Warning: Preferences error: {e}")


# ---------------------------------------------------------------------------
# Launch command resolution (always argv lists, never shell strings)
# ---------------------------------------------------------------------------

_INSTALLED_FLATPAKS_CACHE = None


def get_installed_flatpaks():
    global _INSTALLED_FLATPAKS_CACHE
    if _INSTALLED_FLATPAKS_CACHE is not None:
        return _INSTALLED_FLATPAKS_CACHE
    flatpaks = []
    try:
        out = subprocess.check_output(
            ["flatpak", "list", "--app", "--columns=application"],
            text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT, env=get_env(),
        )
        flatpaks = [line.strip() for line in out.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        pass
    _INSTALLED_FLATPAKS_CACHE = flatpaks
    return flatpaks


# Desktop Entry spec field codes and flatpak's @@ markers, removed from Exec argv
_FIELD_CODE_RE = re.compile(r"^%[fFuUdDnNickvm]$")


def parse_desktop_exec(exec_line):
    """Parses a desktop-entry Exec value into an argv list (or None)."""
    try:
        tokens = shlex.split(exec_line)
    except ValueError:
        return None
    argv = []
    for tok in tokens:
        if _FIELD_CODE_RE.match(tok) or tok.startswith("@@"):
            continue
        tok = re.sub(r"%[fFuUdDnNickvm]", "", tok).replace("%%", "%")
        if tok:
            argv.append(tok)
    return argv or None


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
    # Earlier directories take precedence (user overrides system)
    for d in reversed(desktop_dirs):
        if not os.path.isdir(d):
            continue
        for f in glob.glob(os.path.join(d, "*.desktop")):
            base = os.path.basename(f)[:-8]  # strip .desktop
            wm_class = exec_cmd = name = None
            in_main = False
            try:
                with open(f, "r", errors="ignore") as fp:
                    for line in fp:
                        line = line.strip()
                        if line.startswith("["):
                            in_main = line == "[Desktop Entry]"
                            continue
                        if not in_main:
                            continue
                        if line.startswith("StartupWMClass="):
                            wm_class = line.split("=", 1)[1].strip()
                        elif line.startswith("Exec=") and not exec_cmd:
                            exec_cmd = line.split("=", 1)[1].strip()
                        elif line.startswith("Name=") and not name:
                            name = line.split("=", 1)[1].strip()
            except OSError:
                continue

            argv = parse_desktop_exec(exec_cmd) if exec_cmd else None
            if argv:
                commands[base.lower()] = argv
                if wm_class:
                    commands[wm_class.lower()] = argv
                if name:
                    commands[name.lower()] = argv
                    commands[name.lower().replace(" ", "")] = argv

    _DESKTOP_COMMANDS_CACHE = commands
    return commands


CHROME_FLAGS = ["--restore-last-session", "--disable-session-crashed-bubble", "--no-default-browser-check"]

LAUNCH_MAPPING = {
    "google-chrome": ["flatpak", "run", "com.google.Chrome"] + CHROME_FLAGS,
    "com.google.Chrome": ["flatpak", "run", "com.google.Chrome"] + CHROME_FLAGS,
    "spotify": ["flatpak", "run", "com.spotify.Client"],
    "discord": ["flatpak", "run", "com.discordapp.Discord"],
    "com.discordapp.Discord": ["flatpak", "run", "com.discordapp.Discord"],
    "antigravity": ["/usr/local/bin/antigravity"],
    "antigravity-ide": ["/usr/local/bin/antigravity-ide"],
    "steam": ["steam"],
    "dev.warp.Warp": ["/usr/bin/warp-terminal"],
    "warp": ["/usr/bin/warp-terminal"],
    # Ghostty
    "com.mitchellh.ghostty": ["ghostty"],
    "ghostty": ["ghostty"],
    # OrcaSlicer
    "orca-slicer": ["flatpak", "run", "com.orcaslicer.OrcaSlicer"],
    "OrcaSlicer": ["flatpak", "run", "com.orcaslicer.OrcaSlicer"],
    "com.orcaslicer.OrcaSlicer": ["flatpak", "run", "com.orcaslicer.OrcaSlicer"],
    # BambuStudio & PrusaSlicer
    "bambu-studio": ["flatpak", "run", "com.bambulab.BambuStudio"],
    "BambuStudio": ["flatpak", "run", "com.bambulab.BambuStudio"],
    "com.bambulab.BambuStudio": ["flatpak", "run", "com.bambulab.BambuStudio"],
    "prusa-slicer": ["flatpak", "run", "com.prusa3d.PrusaSlicer"],
    "PrusaSlicer": ["flatpak", "run", "com.prusa3d.PrusaSlicer"],
    "com.prusa3d.PrusaSlicer": ["flatpak", "run", "com.prusa3d.PrusaSlicer"],
    # KiCad & FreeCAD
    "KiCad": ["flatpak", "run", "org.kicad.KiCad"],
    "org.kicad.KiCad": ["flatpak", "run", "org.kicad.KiCad"],
    "FreeCAD": ["flatpak", "run", "org.freecad.FreeCAD"],
    "org.freecad.FreeCAD": ["flatpak", "run", "org.freecad.FreeCAD"],
    # Slack, Obsidian, Signal
    "slack": ["flatpak", "run", "com.slack.Slack"],
    "com.slack.Slack": ["flatpak", "run", "com.slack.Slack"],
    "obsidian": ["flatpak", "run", "md.obsidian.Obsidian"],
    "md.obsidian.Obsidian": ["flatpak", "run", "md.obsidian.Obsidian"],
    "signal": ["flatpak", "run", "org.signal.Signal"],
    "org.signal.Signal": ["flatpak", "run", "org.signal.Signal"],
}


def get_launch_command(app_id):
    """
    Resolves an app_id to an argv list, or None if it cannot be resolved safely.
    Only known mappings, installed desktop entries and installed flatpaks are
    accepted; an arbitrary app_id is never executed as a program name.
    """
    if not isinstance(app_id, str) or not APP_ID_RE.fullmatch(app_id):
        return None

    if app_id in LAUNCH_MAPPING:
        return list(LAUNCH_MAPPING[app_id])

    # 1. Desktop file commands lookup
    desktop_cmds = get_desktop_commands()
    low = app_id.lower()
    if low in desktop_cmds:
        return list(desktop_cmds[low])
    norm = low.replace("-", "").replace("_", "").replace(" ", "")
    if norm in desktop_cmds:
        return list(desktop_cmds[norm])

    # 2. If app_id has dots, try last segment as a desktop entry
    if "." in app_id:
        last_low = app_id.split(".")[-1].lower()
        if last_low in desktop_cmds:
            return list(desktop_cmds[last_low])

    # 3. Installed flatpaks: exact id or exact last-segment match only
    for fp in get_installed_flatpaks():
        fp_norm = fp.lower().replace("-", "").replace("_", "")
        last_seg = fp.split(".")[-1].lower().replace("-", "").replace("_", "")
        if norm == fp_norm or norm == last_seg:
            return ["flatpak", "run", fp]

    return None


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
    if not id1 or not id2 or not isinstance(id1, str) or not isinstance(id2, str):
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


def is_chrome(app_id):
    # Exact match only: Chrome PWAs ("chrome-<id>-Default") are separate apps.
    return app_ids_match(_s(app_id), "google-chrome")


SINGLE_INSTANCE_APPS = {
    "google-chrome", "chromium", "firefox", "brave-browser",
    "spotify", "discord", "com.discordapp.discord",
    "slack", "com.slack.slack",
    "signal", "org.signal.signal",
    "antigravity", "antigravity-ide", "steam",
    "obsidian", "md.obsidian.obsidian",
    "io.podman_desktop.podmandesktop",
}


def is_single_instance(app_id):
    return any(app_ids_match(app_id, s) for s in SINGLE_INSTANCE_APPS)


# ---------------------------------------------------------------------------
# cos-cli helpers
# ---------------------------------------------------------------------------

def run_cos_cli(args):
    cmd = [COS_CLI] + args
    try:
        return subprocess.check_output(cmd, env=get_env(), text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"cos-cli error ({args}): {e}", file=sys.stderr)
        return ""


# group index -> number of existing workspaces (refreshed by get_live_state)
WS_COUNTS = {}


def clamp_workspace(group, ws):
    """Never ask cos-cli to create more than one new workspace beyond what exists."""
    count = WS_COUNTS.get(group)
    if count is None:
        return ws
    return min(ws, count)


def get_live_state():
    """Queries cos-cli info --json and returns dynamic output maps and live (non-ignored) apps."""
    out = run_cos_cli(["info", "--json"])
    try:
        data = json.loads(out)
        if not isinstance(data, dict):
            raise ValueError("unexpected cos-cli output")
    except ValueError as e:
        print(f"Error querying cos-cli info --json: {e}", file=sys.stderr)
        return {}, {}, []

    output_to_group = {}
    WS_COUNTS.clear()
    for wg in data.get("workspace_groups") or []:
        WS_COUNTS[wg.get("index", 0)] = len(wg.get("workspaces") or [])
        for out_name in wg.get("outputs") or []:
            # First group wins: a window straddling outputs can make cos-cli list
            # an output under more than one group.
            output_to_group.setdefault(out_name, wg.get("index", 0))

    output_to_index = {}
    for o in data.get("outputs") or []:
        output_to_index[_s(o.get("name"))] = o.get("index", 0)

    apps = []
    for a in data.get("apps") or []:
        if not isinstance(a, dict) or not isinstance(a.get("index"), int):
            continue
        a["app_id"] = _s(a.get("app_id"))
        a["title"] = _s(a.get("title"))
        if phoenix_profile.is_ignored_app(a["app_id"], a["title"]):
            continue
        apps.append(a)
    return output_to_group, output_to_index, apps


def _window_pos(w):
    out = w["outputs"][0].get("name", "") if w.get("outputs") else ""
    ws = w["workspaces"][0].get("index", -1) if w.get("workspaces") else -1
    return out, ws


def title_similarity_score(t1, t2):
    clean1 = re.sub(r"\s*-\s*Google Chrome.*$", "", _s(t1), flags=re.IGNORECASE).strip().lower()
    clean2 = re.sub(r"\s*-\s*Google Chrome.*$", "", _s(t2), flags=re.IGNORECASE).strip().lower()
    if not clean1 or not clean2:
        return 0
    if clean1 == clean2:
        return 100
    if clean1 in clean2 or clean2 in clean1:
        return 80
    words1 = set(re.findall(r"\w{3,}", clean1))
    words2 = set(re.findall(r"\w{3,}", clean2))
    if not words1 or not words2:
        return 0
    return min(len(words1 & words2) * 15, 75)


def match_windows(saved, live):
    """
    Optimal 1:1 assignment of saved->live windows by title similarity.
    Exhaustive for small sets (typical), greedy beyond that.
    Returns list of (saved_index, live_index, score).
    """
    if not saved or not live:
        return []
    scores = [[title_similarity_score(s.get("title"), l.get("title")) for l in live] for s in saved]
    n_s, n_l = len(saved), len(live)
    k = min(n_s, n_l)
    if max(n_s, n_l) <= 7:
        best, best_total = None, -1
        if n_s <= n_l:
            for perm in itertools.permutations(range(n_l), k):
                total = sum(scores[i][perm[i]] for i in range(k))
                if total > best_total:
                    best, best_total = [(i, perm[i]) for i in range(k)], total
        else:
            for perm in itertools.permutations(range(n_s), k):
                total = sum(scores[perm[j]][j] for j in range(k))
                if total > best_total:
                    best, best_total = [(perm[j], j) for j in range(k)], total
        return [(si, li, scores[si][li]) for si, li in best]

    triples = sorted(((scores[si][li], si, li) for si in range(n_s) for li in range(n_l)), reverse=True)
    used_s, used_l, pairs = set(), set(), []
    for sc, si, li in triples:
        if si not in used_s and li not in used_l:
            used_s.add(si)
            used_l.add(li)
            pairs.append((si, li, sc))
    return pairs


def move_window_and_verify(track_app_id, track_title, target_output, target_ws, placed, timeout=3.0):
    """
    Finds the window using fresh state, executes cos-cli move, and verifies that the compositor
    has moved the window to the expected physical output and workspace.

    `placed` is a Counter of (app_id_lower, title, output, ws) for windows already
    positioned, so that windows with identical titles (e.g. two terminals named
    "fish") are not mistaken for each other.
    Returns (success, last_candidate).
    """
    start_time = time.time()
    candidate = None
    key_app = (track_app_id or "").lower()
    while time.time() - start_time < timeout:
        out_to_group, out_to_idx, live_apps = get_live_state()
        matches = [
            a for a in live_apps
            if app_ids_match(a["app_id"], track_app_id) and (track_title is None or a["title"] == track_title)
        ]
        if not matches:
            time.sleep(0.2)
            continue

        at_target = [a for a in matches if _window_pos(a) == (target_output, target_ws)]
        if len(at_target) > placed[(key_app, track_title, target_output, target_ws)]:
            candidate = at_target[0]
            placed[(key_app, track_title, target_output, target_ws)] += 1
            print(f"Verified: '{candidate['app_id']}' (\"{candidate['title'][:30]}\") at {target_output} ws {target_ws}")
            return True, candidate

        # Prefer a window that is not one we already placed elsewhere
        remaining = collections.Counter(placed)
        candidate = None
        for a in matches:
            pos_key = (key_app, track_title) + _window_pos(a)
            if remaining[pos_key] > 0:
                remaining[pos_key] -= 1
                continue
            candidate = a
            break
        if candidate is None:
            candidate = matches[0]

        target_group = out_to_group.get(target_output)
        target_oidx = out_to_idx.get(target_output)
        if target_group is None:
            print(f"Error: Target screen '{target_output}' not found in active workspace groups.")
            return False, candidate

        eff_ws = clamp_workspace(target_group, target_ws)
        if eff_ws != target_ws:
            print(f"Workspace {target_ws} does not exist on '{target_output}'; using {eff_ws}.")
            target_ws = eff_ws
            continue
        move_cmd = ["move", "-i", str(candidate["index"]), "-g", str(target_group), "-w", str(target_ws)]
        if target_oidx is not None:
            move_cmd.extend(["-o", str(target_oidx)])

        run_cos_cli(move_cmd)
        time.sleep(0.3)

    return False, candidate


def apply_window_state(app_id, title, saved_states):
    if "maximized" in saved_states:
        flag = "--maximize"
    elif "minimized" in saved_states:
        flag = "--minimize"
    else:
        return
    _, _, fresh_apps = get_live_state()
    fresh = next((a for a in fresh_apps if a["title"] == title and app_ids_match(a["app_id"], app_id)), None)
    if fresh:
        run_cos_cli(["state", "-i", str(fresh["index"]), flag])


# ---------------------------------------------------------------------------
# Restore orchestration
# ---------------------------------------------------------------------------

def _normalize_saved(apps):
    out = []
    for a in apps:
        if not isinstance(a, dict):
            continue
        app_id = _s(a.get("app_id")).strip()
        if not app_id or phoenix_profile.is_ignored_app(app_id, _s(a.get("title"))):
            continue
        st = a.get("state")
        out.append({
            "app_id": app_id,
            "title": _s(a.get("title")),
            "state": st if isinstance(st, list) else [],
            "workspace": _ws_index(a.get("workspace")),
            "output_name": _s(a.get("output_name")),
        })
    return out


def _launch(argv, app_id):
    print(f"Spawning application '{app_id}': {shlex.join(argv)}")
    try:
        subprocess.Popen(
            argv, env=get_env(), stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        return True
    except OSError as e:
        print(f"Warning: failed to launch '{app_id}': {e}", file=sys.stderr)
        return False


def restore_session(profile_name=None):
    chosen_profile, reason = phoenix_profile.resolve_profile_for_restore(profile_name)
    print(f"Profile: '{chosen_profile}' ({reason})")

    cfg = phoenix_profile.load_profiles_config()
    if chosen_profile not in cfg.get("profiles", {}):
        print(f"Warning: profile '{chosen_profile}' is not defined in profiles.json.", file=sys.stderr)

    snapshot, target_file = phoenix_profile.load_snapshot(chosen_profile)
    if snapshot is None:
        print(f"No usable snapshot found for profile '{chosen_profile}'.", file=sys.stderr)
        return False

    saved_apps = _normalize_saved(snapshot.get("apps", []))
    if not saved_apps:
        print(f"No apps found in snapshot for profile '{chosen_profile}'.")
        return False

    print(f"Restoring {len(saved_apps)} app windows from profile '{chosen_profile}' snapshot "
          f"({snapshot.get('timestamp_str')}, {target_file})...")
    phoenix_profile.record_profile_action("restore", chosen_profile, reason)

    # Sanitize Chrome Local State & Preferences for auto profile/tab restoration
    if any(is_chrome(a["app_id"]) for a in saved_apps):
        sanitize_chrome_environment()

    # 1. Launch only the windows that are missing (idempotent: re-running a
    #    restore or switching profiles does not duplicate running apps).
    _, _, live_now = get_live_state()
    groups = collections.OrderedDict()
    for app in saved_apps:
        key = next((k for k in groups if app_ids_match(k, app["app_id"])), app["app_id"])
        groups.setdefault(key, []).append(app)

    unlaunchable = set()
    for key, entries in groups.items():
        live_count = sum(1 for l in live_now if app_ids_match(l["app_id"], key))
        needed = (0 if live_count else 1) if is_single_instance(key) else max(0, len(entries) - live_count)
        if not needed:
            continue
        argv = get_launch_command(key)
        if argv is None:
            print(f"Warning: no safe launch command for '{key}'; skipping.", file=sys.stderr)
            if not live_count:
                unlaunchable.add(key)
            continue
        for _ in range(needed):
            _launch(argv, key)
            time.sleep(0.3)

    placeable = [a for a in saved_apps if not any(app_ids_match(a["app_id"], u) for u in unlaunchable)]

    # 2. Poll for live windows to appear and Chrome titles to resolve
    print("Waiting for windows to spawn and titles to resolve...")
    expected_outputs = set(a["output_name"] for a in placeable if a["output_name"])
    saved_chrome_count = sum(1 for a in placeable if is_chrome(a["app_id"]))
    want_counts = collections.Counter()
    for key, entries in groups.items():
        if key not in unlaunchable:
            want_counts[key] = 1 if is_single_instance(key) else len(entries)

    start_time = time.time()
    while time.time() - start_time < WAIT_FOR_WINDOWS_SECONDS:
        time.sleep(1)
        out_to_group, out_to_idx, live_apps = get_live_state()

        # Wait (briefly) for all expected physical outputs; a monitor that is no
        # longer attached must not stall the whole restore.
        missing_outputs = expected_outputs - set(out_to_group.keys())
        if missing_outputs and time.time() - start_time < WAIT_FOR_OUTPUTS_SECONDS:
            continue

        if any(sum(1 for l in live_apps if app_ids_match(l["app_id"], k)) < n for k, n in want_counts.items()):
            continue

        if saved_chrome_count > 0:
            live_chrome = [a for a in live_apps if is_chrome(a["app_id"])]
            if len(live_chrome) < saved_chrome_count:
                continue
            if any(a["title"].strip().lower() in CHROME_LOADING_TITLES for a in live_chrome):
                continue
        break

    out_to_group, out_to_idx, live_apps = get_live_state()
    print(f"Found {len(live_apps)} active windows.")
    print(f"Active Output Map: {out_to_group}")

    fallback_output = None
    if out_to_group:
        fallback_output = min(out_to_group, key=lambda o: (out_to_idx.get(o, 0), o))

    def resolve_output(name):
        if name in out_to_group:
            return name
        if fallback_output:
            print(f"Screen '{name or '(unknown)'}' is not connected; using '{fallback_output}' instead.")
        return fallback_output

    placed = collections.Counter()
    failures = []

    # 3. Chrome: optimal 1:1 title matching between saved and live windows
    chrome_saved = [s for s in placeable if is_chrome(s["app_id"])]
    other_saved = [s for s in placeable if not is_chrome(s["app_id"])]
    live_chrome = [l for l in live_apps if is_chrome(l["app_id"])]

    chrome_pairs = []
    for si, li, score in match_windows(chrome_saved, live_chrome):
        chrome_pairs.append((chrome_saved[si], live_chrome[li]["title"]))
        print(f"Matched Chrome: '{chrome_saved[si]['title'][:30]}' -> Live: '{live_chrome[li]['title'][:30]}' (score {score})")

    # 4. Move Chrome windows dynamically with verification
    for saved, track_title in chrome_pairs:
        target_out = resolve_output(saved["output_name"])
        target_ws = saved["workspace"]
        if target_out is None:
            failures.append(f"google-chrome \"{track_title[:25]}\"")
            continue
        print(f"Positioning Chrome \"{track_title[:25]}\" -> Screen '{target_out}', Workspace {target_ws}")
        success, _ = move_window_and_verify("google-chrome", track_title, target_out, target_ws, placed)
        if not success:
            failures.append(f"google-chrome \"{track_title[:25]}\"")
        apply_window_state("google-chrome", track_title, saved["state"])

    # 5. Move all other applications dynamically with verification
    claimed = collections.Counter()  # (app_id_lower, title) already assigned to a saved entry
    for saved in other_saved:
        app_id = saved["app_id"]
        target_out = resolve_output(saved["output_name"])
        target_ws = saved["workspace"]
        saved_title = saved["title"]

        _, _, live_apps = get_live_state()
        pool = collections.Counter(claimed)
        candidates = []
        for live in live_apps:
            if not app_ids_match(live["app_id"], app_id):
                continue
            k = (app_id.lower(), live["title"])
            if pool[k] > 0:
                pool[k] -= 1
                continue
            candidates.append(live)

        candidate = None
        if saved_title:
            candidate = next((l for l in candidates if l["title"] and
                              (saved_title in l["title"] or l["title"] in saved_title)), None)
        if candidate is None and candidates:
            candidate = candidates[0]

        if not candidate or target_out is None:
            print(f"Warning: Could not find live window for '{app_id}' ({saved_title})")
            failures.append(app_id)
            continue

        claimed[(app_id.lower(), candidate["title"])] += 1
        track_title = candidate["title"] or None

        print(f"Positioning '{app_id}' -> Screen '{target_out}', Workspace {target_ws}")
        success, moved = move_window_and_verify(app_id, track_title, target_out, target_ws, placed)
        if not success:
            failures.append(app_id)
        # Apply window state even if positioning failed
        apply_window_state(app_id, (moved or candidate)["title"], saved["state"])

    # 6. Activate primary workspace on primary screen at end of restoration
    run_cos_cli(["ws-activate", "--workspace", "0"])
    if failures:
        print(f"Restoration finished with {len(failures)} window(s) not placed: {', '.join(failures)}")
    else:
        print("COSMIC desktop session restoration complete.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Restore a Phoenix COSMIC window layout.")
    parser.add_argument("-p", "--profile", dest="profile_opt", default=None, help="Profile to restore")
    parser.add_argument("profile", nargs="?", default=None, help="Profile to restore (positional form)")
    args = parser.parse_args()

    with phoenix_profile.file_lock(phoenix_profile.SESSION_LOCK, blocking=True, timeout=30) as got:
        if not got:
            print("Another restore or save is in progress; aborting.", file=sys.stderr)
            sys.exit(3)
        try:
            ok = restore_session(args.profile_opt or args.profile)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(2)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
