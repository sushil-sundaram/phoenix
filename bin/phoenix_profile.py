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
import copy
import fcntl
import tempfile
import contextlib

PROFILES_CONFIG_DIR = os.path.expanduser("~/.config/cosmic")
PROFILES_CONFIG_FILE = os.path.join(PROFILES_CONFIG_DIR, "profiles.json")
PROFILES_STORAGE_DIR = os.path.join(PROFILES_CONFIG_DIR, "profiles")
PROFILE_STATE_FILE = os.path.join(PROFILES_CONFIG_DIR, "profile-state.json")
LEGACY_SNAPSHOT_FILE = os.path.join(PROFILES_CONFIG_DIR, "session-snapshot.json")
LEGACY_BACKUP_FILE = os.path.join(PROFILES_CONFIG_DIR, "session-snapshot.json.bak")
BIN_DIR = os.path.dirname(os.path.realpath(__file__))

# Timeout (seconds) applied to every external probe/helper command so a hung
# compositor or NetworkManager can never wedge the saver/restorer forever.
CMD_TIMEOUT = 10

# Profile names become directory names; restrict them so they can never escape
# PROFILES_STORAGE_DIR or be parsed as command-line options.
PROFILE_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,31}")

# Windows that are never captured or restored (panel applets, helpers, etc.).
IGNORED_APPS = {"steam", "io.github.k33wee.clippy-land"}


def _resolve_cos_cli():
    """Locates cos-cli: $PHOENIX_COS_CLI, then next to this script, then legacy path, then PATH."""
    candidates = [
        os.environ.get("PHOENIX_COS_CLI"),
        os.path.join(BIN_DIR, "cos-cli"),
        os.path.expanduser("~/phoenix/bin/cos-cli"),
        shutil.which("cos-cli"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return os.path.join(BIN_DIR, "cos-cli")


COS_CLI = _resolve_cos_cli()


def is_ignored_app(app_id, title=""):
    """Single source of truth for windows that should never be saved or restored."""
    low = (app_id or "").lower()
    return low in IGNORED_APPS or "applet" in low or title == "Cosmic - Iced"


def is_valid_profile_name(name):
    return isinstance(name, str) and PROFILE_NAME_RE.fullmatch(name) is not None


def validate_profile_name(name):
    """Raises ValueError if the profile name is unsafe to use as a directory name."""
    if not is_valid_profile_name(name):
        raise ValueError(
            f"Invalid profile name {name!r}: use 1-32 letters, digits, '-' or '_' "
            "(must start with a letter or digit)."
        )
    return name


def atomic_write_json(path, obj, indent=2):
    """Writes JSON to path atomically (unique temp file + fsync + rename), preserving mode."""
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix="." + os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=indent)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.chmod(tmp, os.stat(path).st_mode & 0o7777)
        except FileNotFoundError:
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


def _lock_dir():
    rd = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    if os.path.isdir(rd) and os.access(rd, os.W_OK):
        return rd
    os.makedirs(PROFILES_CONFIG_DIR, exist_ok=True)
    return PROFILES_CONFIG_DIR


@contextlib.contextmanager
def file_lock(name, blocking=True, timeout=30.0):
    """
    Cross-process advisory lock. Yields True if acquired, False if not (non-blocking
    or timed out). Locks are released automatically if the process dies.
    """
    path = os.path.join(_lock_dir(), f"phoenix-{name}.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    acquired = False
    try:
        deadline = time.monotonic() + (timeout if blocking else 0)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(0.1)
        yield acquired
    finally:
        if acquired:
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# Held by the restorer for its whole run and by the saver while it writes, so a
# periodic save can never capture (and overwrite the good snapshot with) a
# half-restored layout.
SESSION_LOCK = "session"
# Short-lived lock guarding read-modify-write of profile-state.json / profiles.json.
STATE_LOCK = "state"

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
    parts = [p for p in env.get("PATH", "").split(":") if p]
    for extra in ["/usr/local/bin", "/usr/bin", f"{home}/.local/bin", f"{home}/.cargo/bin", f"{home}/.pixi/bin"]:
        if extra not in parts:
            parts.append(extra)
    env["PATH"] = ":".join(parts)
    return env

def get_active_wifi_ssids():
    """Returns a list of currently active Wi-Fi SSIDs using NetworkManager CLI."""
    ssids = []
    # 1. Check nmcli active wifi devices
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi", "list", "--rescan", "no"],
            text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT
        )
        for line in out.splitlines():
            if line.startswith("yes:"):
                # nmcli -t escapes ':' and '\\' inside values
                ssid = line.split(":", 1)[1].replace("\\:", ":").replace("\\\\", "\\").strip()
                if ssid and ssid not in ssids:
                    ssids.append(ssid)
    except Exception:
        pass

    # 2. Check active wireless connections
    try:
        out = subprocess.check_output(
            ["nmcli", "-t", "-f", "TYPE,NAME", "con", "show", "--active"],
            text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT
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
            out = subprocess.check_output([COS_CLI, "info", "--json"], env=get_env(), text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT)
            data = json.loads(out)
            for o in data.get("outputs", []):
                name = o.get("name")
                if name and name not in monitors:
                    monitors.append(name)
        except Exception:
            pass

    # 2. Query cosmic-randr for display models and enabled status
    try:
        out = subprocess.check_output(["cosmic-randr", "list"], env=get_env(), text=True, stderr=subprocess.DEVNULL, timeout=CMD_TIMEOUT)
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
                                if f.read().strip() == "connected":
                                    connector = entry.split("-", 1)[-1] if "-" in entry else entry
                                    if connector not in monitors:
                                        monitors.append(connector)
                                        details[connector] = {"status": "enabled"}
                        except Exception:
                            pass
            except Exception:
                pass

    return monitors, models, details

class ConfigError(Exception):
    pass


def load_profiles_config(strict=False):
    """
    Loads profiles configuration from disk, creating default if missing.
    With strict=True a corrupt config raises ConfigError instead of silently
    falling back to defaults (callers that write the config must use strict).
    """
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
        return copy.deepcopy(DEFAULT_PROFILES_CONFIG)

    try:
        with open(PROFILES_CONFIG_FILE, "r") as f:
            cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise ValueError("top-level JSON value is not an object")
            # Ensure required top-level keys
            if not isinstance(cfg.get("profiles"), dict):
                cfg["profiles"] = copy.deepcopy(DEFAULT_PROFILES_CONFIG["profiles"])
            if "default_profile" not in cfg:
                cfg["default_profile"] = "home"
            if "auto_detect" not in cfg:
                cfg["auto_detect"] = True
            return cfg
    except (OSError, ValueError) as e:
        if strict:
            raise ConfigError(f"Failed to read {PROFILES_CONFIG_FILE}: {e}. Fix or remove it first.") from e
        print(f"Warning: Failed to read {PROFILES_CONFIG_FILE}: {e}. Using defaults.", file=sys.stderr)
        return copy.deepcopy(DEFAULT_PROFILES_CONFIG)

def save_profiles_config(cfg):
    """Saves profiles configuration to disk atomically."""
    atomic_write_json(PROFILES_CONFIG_FILE, cfg)

def get_profile_state():
    """Returns profile state dict (active, last booted, last saved profile)."""
    if os.path.exists(PROFILE_STATE_FILE):
        try:
            with open(PROFILE_STATE_FILE, "r") as f:
                state = json.load(f)
            if isinstance(state, dict):
                # Never trust a profile name read back from disk
                for k in ("active_profile", "last_booted_profile", "last_saved_profile", "last_restored_profile"):
                    if k in state and not is_valid_profile_name(state[k]):
                        state.pop(k)
                return state
        except (OSError, ValueError):
            pass

    default_p = DEFAULT_PROFILES_CONFIG["default_profile"]
    try:
        with open(PROFILES_CONFIG_FILE, "r") as f:
            cand = json.load(f).get("default_profile", default_p)
            if is_valid_profile_name(cand):
                default_p = cand
    except (OSError, ValueError, AttributeError):
        pass

    return {
        "active_profile": default_p,
        "last_booted_profile": default_p,
        "last_saved_profile": default_p,
        "last_restored_profile": default_p,
        "last_action": "init",
        "last_action_timestamp": time.time(),
        "last_action_reason": "default initialization",
        "history": []
    }

def save_profile_state(state):
    """Saves profile state to disk atomically."""
    atomic_write_json(PROFILE_STATE_FILE, state)

def record_profile_action(action, profile, reason=""):
    """Records a profile action (switch, save, restore) into persistent state history."""
    validate_profile_name(profile)
    with file_lock(STATE_LOCK, timeout=10) as got:
        if not got:
            print("Warning: profile state is locked by another process; recording anyway.", file=sys.stderr)
        _record_profile_action_locked(action, profile, reason)


def _record_profile_action_locked(action, profile, reason):
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
    if cur_details:
        # Only count outputs that are actually lit (a closed laptop lid shows up as
        # a disabled eDP connector and must not count toward monitor rules).
        enabled_count = len([m for m, d in cur_details.items() if d.get("status") == "enabled"])
    else:
        enabled_count = len(cur_monitors)

    min_m = p.get("min_monitors")
    if min_m is not None and enabled_count < min_m:
        return 0, [f"disqualified: {enabled_count} monitors < min {min_m}"]

    max_m = p.get("max_monitors")
    if max_m is not None and enabled_count > max_m:
        return 0, [f"disqualified: {enabled_count} monitors > max {max_m}"]

    # 1. Wi-Fi Matching (Strong signal: +100 exact; +80 partial only if the
    #    profile opts in with "wifi_partial_match": true, since substring
    #    matching lets any nearby AP named e.g. "Iambored_x" select the profile)
    wifi_targets = [t for t in p.get("wifi_ssids", []) if isinstance(t, str) and t.strip()]
    allow_partial = bool(p.get("wifi_partial_match", False))
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
            elif allow_partial and (tw_low in cw_low or cw_low in tw_low):
                score += 80
                reasons.append(f"Wi-Fi partial match: '{cw}'")
                matched = True
                break
        if matched:
            break

    # 2. Monitor Output Connector Matching (+40 each)
    mon_targets = p.get("monitors", [])
    for tm in mon_targets:
        if tm in cur_monitors and cur_details.get(tm, {}).get("status", "enabled") == "enabled":
            score += 40
            reasons.append(f"Monitor connector: '{tm}'")

    # 3. Monitor Hardware Model Matching (+30 each)
    model_targets = [t for t in p.get("monitor_models", []) if isinstance(t, str) and t.strip()]
    if cur_details:
        live_models = [d.get("model", "") for d in cur_details.values()
                       if d.get("status", "enabled") == "enabled" and d.get("model")]
        if not live_models and not any("model" in d for d in cur_details.values()):
            live_models = list(cur_models)
    else:
        live_models = list(cur_models)
    for t_mod in model_targets:
        for cm in live_models:
            # The configured model must appear in the reported one (not the
            # reverse, or a bare "LG" would match "LG ULTRAWIDE").
            if t_mod.lower() in cm.lower():
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

    best_prio = None
    for name, p in cfg.get("profiles", {}).items():
        if not is_valid_profile_name(name) or not isinstance(p, dict):
            continue
        sc, r = score_profile(name, p, cur_wifi, cur_monitors, cur_models, cur_details)
        prio = p.get("priority", 0)
        # Ties are broken by priority, then by config order (first wins)
        if sc > best_score or (sc == best_score and sc > 0 and best_prio is not None and prio > best_prio):
            best_score = sc
            best_profile = name
            best_reasons = r
            best_prio = prio

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
        validate_profile_name(explicit_profile)
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
    if not is_valid_profile_name(last_profile):
        last_profile = DEFAULT_PROFILES_CONFIG["default_profile"]
    return last_profile, f"brought up last saved/booted profile '{last_profile}' (no auto-detect match)"

def resolve_profile_for_save(explicit_profile=None):
    """
    Determines which profile to save to:
    1. Explicit profile if passed.
    2. Active profile from state.
    3. Auto-detected profile or default.
    """
    if explicit_profile:
        return validate_profile_name(explicit_profile)

    state = get_profile_state()
    active = state.get("active_profile")
    if active:
        return active

    cfg = load_profiles_config()
    if cfg.get("auto_detect", True):
        detected, score, _, _ = detect_profile()
        if detected and score > 0:
            return detected

    default_p = cfg.get("default_profile", "home")
    return default_p if is_valid_profile_name(default_p) else DEFAULT_PROFILES_CONFIG["default_profile"]

def get_snapshot_paths(profile_name, create=False):
    """
    Returns dict with 'snapshot', 'backup', and 'dir' for the given profile.
    Side-effect free unless create=True (which only creates the directory).
    The one-time legacy-snapshot migration happens in load_profiles_config(),
    and only into the default profile.
    """
    validate_profile_name(profile_name)
    base = os.path.realpath(PROFILES_STORAGE_DIR)
    pdir = os.path.join(base, profile_name)
    if os.path.realpath(pdir) != pdir or os.path.dirname(pdir) != base:
        raise ValueError(f"Profile directory for {profile_name!r} escapes {base}")
    if create:
        os.makedirs(pdir, mode=0o700, exist_ok=True)
    return {
        "snapshot": os.path.join(pdir, "session-snapshot.json"),
        "backup": os.path.join(pdir, "session-snapshot.json.bak"),
        "dir": pdir,
    }


def _valid_snapshot(data):
    return isinstance(data, dict) and isinstance(data.get("apps"), list)


def load_snapshot(profile_name):
    """
    Loads a profile's snapshot, falling back to its .bak if the primary file is
    missing or corrupt. Never falls back to another profile's data.
    Returns (snapshot_dict, path) or (None, None).
    """
    paths = get_snapshot_paths(profile_name)
    for path in (paths["snapshot"], paths["backup"]):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print(f"Warning: snapshot {path} unreadable ({e}); trying backup.", file=sys.stderr)
            continue
        if _valid_snapshot(data):
            return data, path
        print(f"Warning: snapshot {path} has unexpected structure; trying backup.", file=sys.stderr)
    return None, None
