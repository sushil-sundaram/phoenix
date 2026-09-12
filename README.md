# Phoenix: COSMIC Session Restorer

Phoenix is a robust session restoration tool for the COSMIC Desktop Environment. Like a mythical bird rising from its ashes, Phoenix takes a snapshot of all active application windows across all workspaces and displays, and accurately restores them on boot exactly where you left them.

## Features
- **Intelligent Display Mapping:** Maps windows back to their correct physical displays (`eDP-2`, `DP-9`, etc.) regardless of how Wayland assigns workspace group numbers on boot.
- **XWayland & Wayland Support:** Automatically handles Wayland applications and XWayland applications (e.g., `KiCad`, `FreeCAD`) even when their `app_id` is empty by fuzzy matching against the application title.
- **Clean Chrome Restoration:** Sanitizes Chrome preferences to cleanly restore tabs without showing crash dialogues or profile pickers.
- **Custom Tooling:** Ships with a custom, modified build of `cos-cli` that enhances window title matching.

## Architecture
- `bin/cosmic-session-saver.py`: Runs automatically during system shutdown via a systemd user service. Parses output from `cos-cli info` and generates a snapshot at `~/.config/cosmic/session-snapshot.json`.
- `bin/cosmic-session-restorer.py`: Runs automatically during boot via an XDG autostart `.desktop` file. Waits for displays to be discovered, then spawns the applications and moves them to their saved workspace.
- `bin/cosmic-session-restore.sh`: A simple shell wrapper to set up environments and log output for the restorer.
- `src/cos-cli`: The modified Rust source code for the COSMIC command-line tool which adds title fallback matching.

## Setup Instructions

The system expects this project to be located at `~/phoenix`. Follow these steps to set up the services and enable session restoration:

### 1. Make Scripts Executable
First, ensure that all the scripts in the `bin/` directory have executable permissions:
```bash
chmod +x ~/phoenix/bin/cosmic-session-restore.sh
chmod +x ~/phoenix/bin/cosmic-session-restorer.py
chmod +x ~/phoenix/bin/cosmic-session-saver.py
```

### 2. Configure the Autostart Restorer
Create an XDG autostart `.desktop` file so the session is restored on boot.
```bash
mkdir -p ~/.config/autostart
cat <<EOF > ~/.config/autostart/cosmic-session-restore.desktop
[Desktop Entry]
Type=Application
Exec=/home/\$USER/phoenix/bin/cosmic-session-restore.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=COSMIC Session Restorer
Comment=Restores windows on login
EOF
```

### 3. Configure the Shutdown Saver Service
Set up a systemd user service that triggers during system shutdown or reboot to save your session.
```bash
mkdir -p ~/.config/systemd/user
cat <<EOF > ~/.config/systemd/user/cosmic-session-saver-shutdown.service
[Unit]
Description=Save COSMIC session before shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env python3 /home/%u/phoenix/bin/cosmic-session-saver.py
TimeoutStartSec=10

[Install]
WantedBy=shutdown.target reboot.target halt.target
EOF
```

### 4. Enable and Start the Systemd Service
Reload the systemd user daemon and enable the service so it runs automatically.
```bash
systemctl --user daemon-reload
systemctl --user enable cosmic-session-saver-shutdown.service
```

That's it! Your COSMIC session state will now be seamlessly saved on shutdown and restored when you log back in.
