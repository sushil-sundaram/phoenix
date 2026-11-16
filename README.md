# Phoenix: COSMIC Session Restorer & Profile Manager

Phoenix is a robust session restoration and profile management system for the COSMIC Desktop Environment. Like a mythical bird rising from its ashes, Phoenix captures snapshots of all active application windows across all workspaces and physical displays, and restores them accurately on boot or profile switch.

## Key Features

- **Fedora 44 COSMIC Panel Applet:** A native panel button with a distinctive symbolic Phoenix icon. Click the icon on your panel anytime to pop open an interactive GTK4 / Libadwaita layout switcher showing live hardware detection, one-click layout switching with immediate window restoration, and new profile creation.
- **Profile Support (Home, Work, Mobile, Custom):** Maintain distinct window layouts and application sets for different contexts (e.g. `home` dual-monitor layout vs `work` office layout vs `mobile` laptop-only).
- **Intelligent Auto-Detection:** Automatically detects the appropriate profile upon boot or restart by scoring connected Wi-Fi SSIDs and attached display hardware (display connectors, monitor make/models, monitor counts).
- **Last Booted/Saved Profile Fallback:** If you boot in an unfamiliar environment without a matching profile rule, Phoenix seamlessly restores your last booted/saved profile.
- **Dynamic Live Index Resolution:** Queries live Wayland compositor state before every move, eliminating window-index drift and preventing scrambled windows.
- **Bipartite Tab Matching for Chrome:** Matches multi-window Chrome sessions back to their exact intended screens and workspaces using tab title tokens.
- **Clean Chrome Restoration:** Sanitizes Chrome preferences to cleanly restore tabs without showing crash dialogues or profile pickers.
- **Unified CLI (`phoenix`):** A command-line utility to inspect status, switch profiles, save snapshots, and test auto-detection rules.

## Architecture

- `bin/phoenix`: The unified CLI command for managing profiles, status, saving, restoring, and panel applet installation.
- `bin/phoenix-popup`: The interactive GTK4/Libadwaita popup switcher invoked by the panel applet button or CLI (`phoenix popup`).
- `bin/generate_icons.py`: Generates the Phoenix vector symbolic icon (`phoenix-profile-symbolic.svg`), full-color application logo (`phoenix-profile.svg`), and multi-size rasterized PNGs.
- `bin/phoenix_profile.py`: The core profile engine managing environment probing, detection scoring, and persistent state (`~/.config/cosmic/profile-state.json`).
- `bin/cosmic-session-saver.py`: Captures active windows and saves snapshots to the active profile's storage directory (`~/.config/cosmic/profiles/<profile>/session-snapshot.json`). Runs periodically every 3 minutes via systemd timer and automatically before shutdown/reboot.
- `bin/cosmic-session-restorer.py`: Evaluates auto-detection, loads the appropriate profile's snapshot, launches applications, and dynamically moves windows to their physical displays and workspaces.
- `bin/cosmic-session-restore.sh`: Shell wrapper triggered by XDG autostart on user login.
- `src/cos-cli`: The modified Rust COSMIC CLI tool providing JSON-RPC toplevel management.
- `config/profiles.default.json`: Default profile definitions template. User configuration lives at `~/.config/cosmic/profiles.json`.

## Quick CLI Reference

```bash
# Check current profile, auto-detected profile, wifi, and connected displays
phoenix status

# List all configured profiles and their triggers
phoenix profile list

# Test environment detection rules and inspect scoring
phoenix profile detect

# Switch active profile manually (add -r to immediately restore layout)
phoenix profile switch work
phoenix profile switch home --restore

# Save the current window state to a specific profile (or active profile)
phoenix profile save work
phoenix save

# Restore windows from a specific profile (or auto-detected/last)
phoenix profile restore home
phoenix restore

# Add a new profile and optionally learn current Wi-Fi and monitors
phoenix profile add office --learn --desc "Office workstation"

# Toggle the Phoenix profile popup switcher GUI
phoenix popup

# Manage the COSMIC Panel Applet
phoenix applet status
phoenix applet install
phoenix applet uninstall
```

## Profile Configuration (`~/.config/cosmic/profiles.json`)

Phoenix configures profiles using JSON rules:

```json
{
  "version": 1,
  "auto_detect": true,
  "default_profile": "home",
  "profiles": {
    "home": {
      "description": "Home dual-monitor setup (Ultrawide + Vertical Lenovo)",
      "wifi_ssids": [
        "Airtel_Iamextremelybored",
        "Airtel_Iamverybored",
        "Iambored"
      ],
      "monitors": ["DP-2", "DP-9"],
      "monitor_models": ["LEN S24e-10", "LG ULTRAWIDE"],
      "min_monitors": 2,
      "priority": 10
    },
    "work": {
      "description": "Work office environment / corporate network",
      "wifi_ssids": ["Xook FoodMaking"],
      "monitors": [],
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
```

## Setup Instructions

The system expects this project to be located at `~/phoenix`.

### 1. Ensure Scripts are Executable and Symlinked
```bash
chmod +x ~/phoenix/bin/*
ln -sfn ~/phoenix/bin/phoenix ~/.local/bin/phoenix
ln -sfn ~/phoenix/bin/cosmic-session-restore.sh ~/.local/bin/cosmic-session-restore.sh
ln -sfn ~/phoenix/bin/cosmic-session-restorer.py ~/.local/bin/cosmic-session-restorer.py
ln -sfn ~/phoenix/bin/cosmic-session-saver.py ~/.local/bin/cosmic-session-saver.py
```

### 2. Autostart Restorer
Created at `~/.config/autostart/cosmic-session-restore.desktop`:
```ini
[Desktop Entry]
Type=Application
Exec=/home/sushil-s/phoenix/bin/cosmic-session-restore.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=COSMIC Session Restorer
Comment=Restores windows on login
```

### 3. Periodic and Shutdown Systemd Services
- `cosmic-session-saver.timer`: Runs every 3 minutes (`OnCalendar=*:0/3`).
- `cosmic-session-saver-shutdown.service`: Runs `ExecStop` when logging out or shutting down.
```bash
systemctl --user daemon-reload
systemctl --user enable --now cosmic-session-saver.timer
systemctl --user enable cosmic-session-saver-shutdown.service
```

### 4. Install the COSMIC Panel Applet
Install the Phoenix panel button, icons, and register it directly onto your top panel:
```bash
phoenix applet install
```
The Phoenix icon will appear immediately in your COSMIC panel. Clicking it toggles the interactive profile switcher where you can view your detected environment, click any profile to switch and restore layouts, or save your active layout.
