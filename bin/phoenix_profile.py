#!/usr/bin/env python3
"""
Phoenix Profile Engine
Handles profile configuration, environment probing (Wi-Fi SSIDs, connected monitors, display models),
scoring-based auto-detection, and profile state persistence (last booted/saved profile).
"""

import os
import sys
import json
import subprocess
import re
import time
import shutil

PROFILES_CONFIG_DIR = os.path.expanduser("~/.config/cosmic")
PROFILES_CONFIG_FILE = os.path.join(PROFILES_CONFIG_DIR, "profiles.json")
PROFILES_STORAGE_DIR = os.path.join(PROFILES_CONFIG_DIR, "profiles")
PROFILE_STATE_FILE = os.path.join(PROFILES_CONFIG_DIR, "profile-state.json")
LEGACY_SNAPSHOT_FILE = os.path.join(PROFILES_CONFIG_DIR, "session-snapshot.json")
LEGACY_BACKUP_FILE = os.path.join(PROFILES_CONFIG_DIR, "session-snapshot.json.bak")
COS_CLI = os.path.expanduser("~/phoenix/bin/cos-cli")

DEFAULT_PROFILES_CONFIG = {
    "version": 1,
    "auto_detect": True,
    "default_profile": "home",
    "profiles": {
        "home": {
            "description": "Home dual-monitor setup (Ultrawide + Vertical Lenovo)",
            "wifi_ssids": [
                "Airtel_Iamextremelybored",
                "Airtel_Iamverybored",
                "Airtel_Iamverybored_5G",
                "Iambored"
            ],
            "monitors": ["DP-2", "DP-9"],
            "monitor_models": ["LEN S24e-10", "LG ULTRAWIDE"],
            "min_monitors": 2,
            "priority": 10
        },
        "work": {
            "description": "Work office environment / corporate network",
            "wifi_ssids": [
                "Xook FoodMaking"
            ],
            "monitors": [],
            "monitor_models": [],
            "min_monitors": 1,
            "priority": 10
        },
        "mobile": {
            "description": "Laptop internal display only on-the-go",
            "wifi_ssids": [],
            "monitors": ["eDP-2", "eDP-1"],
            "monitor_models": ["0x0A55"],
            "max_monitors": 1,
            "priority": 5
        }
    }
}

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

def get_active_wifi_ssids():
    """Returns a list of currently active Wi-Fi SSIDs using NetworkManager CLI."""
    ssids = []
    # 1. Check nmcli active wifi devices
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if line.startswith("yes:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid and ssid not in ssids:
                    ssids.append(ssid)
    except Exception:
        pass

    # 2. Check active wireless connections
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "TYPE,NAME", "con", "show", "--active"],
            text=True, stderr=subprocess.DEVNULL
        )
        for line in out.splitlines():
            if line.startswith("802-11-wireless:"):
                ssid = line.split(":", 1)[1].strip()
                if ssid and ssid not in ssids:
                    ssids.append(ssid)
    except Exception:
        pass

    return ssids

def get_connected_monitors():
    """
    Returns (monitors, models, details)
    Combines cosmic-randr, cos-cli, and /sys/class/drm to accurately identify
    connected display ports and monitor hardware models.
    """
    monitors = []
    models = []
    details = {}

    # 1. Query cos-cli if available
    if os.path.exists(COS_CLI):
        try:
            out = subprocess.check_output([COS_CLI, "info", "--json"], env=get_env(), text=True, stderr=subprocess.DEVNULL)
            data = json.loads(out)
            for o in data.get("outputs", []):
                name = o.get("name")
                if name and name not in monitors:
                    monitors.append(name)
        except Exception:
            pass

    # 2. Query cosmic-randr for display models and enabled status
    try:
        out = subprocess.check_output(["cosmic-randr", "list"], env=get_env(), text=True, stderr=subprocess.DEVNULL)
        clean = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", out)
        cur = None
        for line in clean.splitlines():
            line = line.strip()
            m_header = re.match(r"^([\w\-]+)\s+\((enabled|disabled)\)", line)
            if m_header:
                cur = m_header.group(1)
                details[cur] = {"status": m_header.group(2)}
                if cur not in monitors:
                    monitors.append(cur)
            elif cur and ":" in line:
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip()
                if k in ["make", "model"]:
                    details[cur][k] = v
                    if k == "model" and v and v not in models:
                        models.append(v)
    except Exception:
        pass

    # 3. Direct DRM status fallback if userland tools didn't report monitors
    if not monitors:
        drm_path = "/sys/class/drm"
        if os.path.isdir(drm_path):
            try:
                for entry in os.listdir(drm_path):
                    status_file = os.path.join(drm_path, entry, "status")
                    if os.path.isfile(status_file):
                        try:
                            with open(status_file, "r") as f:
                                if "connected" in f.read():
                                    connector = entry.split("-", 1)[-1] if "-" in entry else entry
                                    if connector not in monitors:
                                        monitors.append(connector)
                                        details[connector] = {"status": "enabled"}
                        except Exception:
                            pass
            except Exception:
                pass

    return monitors, models, details

def load_profiles_config():
    """Loads profiles configuration from disk, creating default if missing."""
    os.makedirs(PROFILES_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(PROFILES_CONFIG_FILE):
        save_profiles_config(DEFAULT_PROFILES_CONFIG)
        # Seed initial home snapshot if legacy snapshot exists
        home_dir = os.path.join(PROFILES_STORAGE_DIR, "home")
        os.makedirs(home_dir, exist_ok=True)
        home_snapshot = os.path.join(home_dir, "session-snapshot.json")
        if os.path.exists(LEGACY_SNAPSHOT_FILE) and not os.path.exists(home_snapshot):
            try:
                shutil.copy2(LEGACY_SNAPSHOT_FILE, home_snapshot)
                if os.path.exists(LEGACY_BACKUP_FILE):
                    shutil.copy2(LEGACY_BACKUP_FILE, os.path.join(home_dir, "session-snapshot.json.bak"))
            except Exception:
                pass
        return DEFAULT_PROFILES_CONFIG.copy()

    try:
        with open(PROFILES_CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            # Ensure required top-level keys
            if "profiles" not in cfg:
                cfg["profiles"] = DEFAULT_PROFILES_CONFIG["profiles"].copy()
            if "default_profile" not in cfg:
                cfg["default_profile"] = "home"
            if "auto_detect" not in cfg:
                cfg["auto_detect"] = True
            return cfg
    except Exception as e:
        print(f"Warning: Failed to read {PROFILES_CONFIG_FILE}: {e}. Using defaults.", file=sys.stderr)
        return DEFAULT_PROFILES_CONFIG.copy()

def save_profiles_config(cfg):
    """Saves profiles configuration to disk atomically."""
    os.makedirs(PROFILES_CONFIG_DIR, exist_ok=True)
    tmp_path = PROFILES_CONFIG_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp_path, PROFILES_CONFIG_FILE)

def get_profile_state():
    """Returns profile state dict (active, last booted, last saved profile)."""
    if os.path.exists(PROFILE_STATE_FILE):
        try:
            with open(PROFILE_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "active_profile": "home",
        "last_booted_profile": "home",
        "last_saved_profile": "home",
        "last_restored_profile": "home",
        "last_action": "init",
        "last_action_timestamp": time.time(),
        "last_action_reason": "default initialization",
        "history": []
    }

def save_profile_state(state):
    """Saves profile state to disk atomically."""
    os.makedirs(PROFILES_CONFIG_DIR, exist_ok=True)
    tmp_path = PROFILE_STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp_path, PROFILE_STATE_FILE)

def record_profile_action(action, profile, reason=""):
    """Records a profile action (switch, save, restore) into persistent state history."""
    state = get_profile_state()
    state["active_profile"] = profile
    state["last_action"] = action
    state["last_action_timestamp"] = time.time()
    state["last_action_reason"] = reason

    if action == "restore" or action == "boot":
        state["last_booted_profile"] = profile
        state["last_restored_profile"] = profile
    elif action == "save":
        state["last_saved_profile"] = profile

    entry = {
        "timestamp": time.time(),
        "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "action": action,
        "profile": profile,
        "reason": reason
    }
    history = state.get("history", [])
    history.append(entry)
    state["history"] = history[-50:]  # Keep last 50 events
    save_profile_state(state)

def score_profile(name, p, cur_wifi, cur_monitors, cur_models, cur_details):
    """
    Evaluates how strongly the current environment matches a profile definition.
    Returns (score, reasons_list).
    """
    score = 0
    reasons = []

    # Monitor count constraints
    enabled_count = len([m for m, d in cur_details.items() if d.get("status") == "enabled"])
    if not enabled_count:
        enabled_count = len(cur_monitors)

    min_m = p.get("min_monitors")
    if min_m is not None and enabled_count < min_m:
        return 0, [f"disqualified: {enabled_count} monitors < min {min_m}"]

    max_m = p.get("max_monitors")
    if max_m is not None and enabled_count > max_m:
        return 0, [f"disqualified: {enabled_count} monitors > max {max_m}"]

    # 1. Wi-Fi Matching (Strong signal: +100 exact, +80 substring)
    wifi_targets = p.get("wifi_ssids", [])
    for cw in cur_wifi:
        cw_low = cw.lower()
        matched = False
        for tw in wifi_targets:
            tw_low = tw.lower()
            if tw_low == cw_low:
                score += 100
                reasons.append(f"Wi-Fi match: '{cw}'")
                matched = True
                break
            elif tw_low in cw_low or cw_low in tw_low:
                score += 80
                reasons.append(f"Wi-Fi partial match: '{cw}'")
                matched = True
                break
        if matched:
            break

    # 2. Monitor Output Connector Matching (+40 each)
    mon_targets = p.get("monitors", [])
    for tm in mon_targets:
        if tm in cur_monitors:
            score += 40
            reasons.append(f"Monitor connector: '{tm}'")

    # 3. Monitor Hardware Model Matching (+30 each)
    model_targets = p.get("monitor_models", [])
    for t_mod in model_targets:
        for cm in cur_models:
            if t_mod.lower() in cm.lower() or cm.lower() in t_mod.lower():
                score += 30
                reasons.append(f"Monitor model: '{cm}'")
                break

    # 4. Profile Priority (+priority)
    prio = p.get("priority", 0)
    if score > 0 and prio:
        score += prio

    return score, reasons

def detect_profile():
    """
    Probes the active network and display hardware and returns the best matching profile.
    Returns (profile_name, score, reasons, env_dict).
    """
    cfg = load_profiles_config()
    cur_wifi = get_active_wifi_ssids()
    cur_monitors, cur_models, cur_details = get_connected_monitors()

    env_dict = {
        "wifi": cur_wifi,
        "monitors": cur_monitors,
        "models": cur_models,
        "details": cur_details
    }

    best_profile = None
    best_score = 0
    best_reasons = []

    for name, p in cfg.get("profiles", {}).items():
        sc, r = score_profile(name, p, cur_wifi, cur_monitors, cur_models, cur_details)
        if sc > best_score:
            best_score = sc
            best_profile = name
            best_reasons = r

    return best_profile, best_score, best_reasons, env_dict

def resolve_profile_for_restore(explicit_profile=None):
    """
    Determines which profile to restore:
    1. If explicit_profile passed, use it.
    2. If auto_detect enabled in config and a profile matches the environment, use it.
    3. Otherwise, bring up the last booted / saved profile from state.
    4. Fall back to default_profile.
    Returns (profile_name, resolution_reason).
    """
    cfg = load_profiles_config()
    state = get_profile_state()
    default_p = cfg.get("default_profile", "home")

    if explicit_profile:
        return explicit_profile, f"explicitly specified: '{explicit_profile}'"

    if cfg.get("auto_detect", True):
        detected, score, reasons, _ = detect_profile()
        if detected and score > 0:
            return detected, f"auto-detected (score {score}: {', '.join(reasons)})"

    # Fallback to last booted / restarted / saved profile
    last_profile = (
        state.get("last_booted_profile")
        or state.get("last_saved_profile")
        or state.get("active_profile")
        or default_p
    )
    return last_profile, f"brought up last saved/booted profile '{last_profile}' (no auto-detect match)"

def resolve_profile_for_save(explicit_profile=None):
    """
    Determines which profile to save to:
    1. Explicit profile if passed.
    2. Active profile from state.
    3. Auto-detected profile or default.
    """
    if explicit_profile:
        return explicit_profile

    state = get_profile_state()
    active = state.get("active_profile")
    if active:
        return active

    cfg = load_profiles_config()
    if cfg.get("auto_detect", True):
        detected, score, _, _ = detect_profile()
        if detected and score > 0:
            return detected

    return cfg.get("default_profile", "home")

def get_snapshot_paths(profile_name):
    """
    Returns dict with 'snapshot', 'backup', and 'dir' for the given profile.
    Automatically migrates legacy snapshot if the profile snapshot doesn't exist yet.
    """
    pdir = os.path.join(PROFILES_STORAGE_DIR, profile_name)
    os.makedirs(pdir, exist_ok=True)
    snap = os.path.join(pdir, "session-snapshot.json")
    bak = os.path.join(pdir, "session-snapshot.json.bak")

    # Transparent migration from legacy snapshot if new profile snapshot doesn't exist yet
    if not os.path.exists(snap) and os.path.exists(LEGACY_SNAPSHOT_FILE):
        try:
            shutil.copy2(LEGACY_SNAPSHOT_FILE, snap)
            if os.path.exists(LEGACY_BACKUP_FILE):
                shutil.copy2(LEGACY_BACKUP_FILE, bak)
        except Exception:
            pass

    return {
        "snapshot": snap,
        "backup": bak,
        "dir": pdir
    }

def sync_legacy_snapshot(source_snapshot_path):
    """Keeps ~/.config/cosmic/session-snapshot.json in sync with active profile for backward compatibility."""
    if os.path.exists(source_snapshot_path):
        try:
            shutil.copy2(source_snapshot_path, LEGACY_SNAPSHOT_FILE)
            src_bak = source_snapshot_path + ".bak"
            if os.path.exists(src_bak):
                shutil.copy2(src_bak, LEGACY_BACKUP_FILE)
        except Exception:
            pass
