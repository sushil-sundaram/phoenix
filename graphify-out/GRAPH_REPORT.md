# Graph Report - phoenix  (2026-11-16)

## Corpus Check
- 17 files · ~15,739 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 287 nodes · 552 edges · 19 communities (15 shown, 4 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0507dd85`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- server.rs
- Commands
- .event
- phoenix_profile.py
- AppState
- find_apps
- rules/graphify.md
- cosmic-session-restorer.py
- workflows/graphify.md
- cosmic-session-restore.sh
- Phoenix: COSMIC Session Restorer & Profile Manager
- cosmic-session-saver.py
- phoenix
- cos-cli
- WorkspaceLayoutsPopup
- main.rs
- String
- NamedHandle
- generate_icons.py

## God Nodes (most connected - your core abstractions)
1. `AppState` - 20 edges
2. `AppState` - 15 edges
3. `find_apps()` - 14 edges
4. `WaylandThread` - 14 edges
5. `JsonInfo` - 11 edges
6. `CliError` - 10 edges
7. `App` - 10 edges
8. `discover()` - 10 edges
9. `main()` - 10 edges
10. `run()` - 10 edges

## Surprising Connections (you probably didn't know these)
- `BackendResponse` --references--> `JsonInfo`  [EXTRACTED]
  src/cos-cli/src/server.rs → src/cos-cli/src/main.rs

## Import Cycles
- None detected.

## Communities (19 total, 4 thin omitted)

### Community 0 - "server.rs"
Cohesion: 0.13
Nodes (31): Arc, Drop, JoinHandle, ActivateParams, ActivateWsParams, BackendRequest, BackendRequestParams, BackendResponse (+23 more)

### Community 1 - "Commands"
Cohesion: 0.08
Nodes (22): `activate`, `close`, Example: Pin apps to fixed workspaces (Python), `info`, JSON-RPC Server Mode, Methods, `move`, Notifications (+14 more)

### Community 2 - ".event"
Cohesion: 0.14
Nodes (21): Dispatch, Event, QueueHandle, AppState, bind(), AppState, Connection, ExtWorkspaceGroupHandleV1 (+13 more)

### Community 3 - "phoenix_profile.py"
Cohesion: 0.11
Nodes (27): detect_profile(), get_active_wifi_ssids(), get_connected_monitors(), get_env(), get_profile_state(), get_snapshot_paths(), load_profiles_config(), Returns (monitors, models, details) Combines cosmic-randr, cos-cli, and… (+19 more)

### Community 4 - "AppState"
Cohesion: 0.13
Nodes (15): HashMap, Item, Iterator, ObjectId, AppState, HandleMap, ExtWorkspaceGroupHandleV1, ExtWorkspaceHandleV1 (+7 more)

### Community 5 - "find_apps"
Cohesion: 0.17
Nodes (16): Debug, Display, Formatter, CliError, discover(), find_apps(), init_tracing(), main() (+8 more)

### Community 7 - "cosmic-session-restorer.py"
Cohesion: 0.29
Nodes (14): app_ids_match(), get_desktop_commands(), get_env(), get_installed_flatpaks(), get_launch_command(), get_live_state(), move_window_and_verify(), Queries cos-cli info --json and returns dynamic output maps and live apps. (+6 more)

### Community 9 - "cosmic-session-restore.sh"
Cohesion: 0.50
Nodes (3): PATH, cosmic-session-restore.sh script, XDG_RUNTIME_DIR

### Community 10 - "Phoenix: COSMIC Session Restorer & Profile Manager"
Cohesion: 0.18
Nodes (10): 1. Ensure Scripts are Executable and Symlinked, 2. Autostart Restorer, 3. Periodic and Shutdown Systemd Services, 4. Install the COSMIC Panel Applet, Architecture, Key Features, Phoenix: COSMIC Session Restorer & Profile Manager, Profile Configuration (`~/.config/cosmic/profiles.json`) (+2 more)

### Community 11 - "cosmic-session-saver.py"
Cohesion: 0.70
Nodes (4): capture_session(), get_env(), main(), save_session()

### Community 12 - "phoenix"
Cohesion: 0.11
Nodes (25): cmd_applet_install(), cmd_applet_status(), cmd_applet_uninstall(), cmd_popup(), cmd_profile_add(), cmd_profile_detect(), cmd_profile_edit(), cmd_profile_list() (+17 more)

### Community 14 - "WorkspaceLayoutsPopup"
Cohesion: 0.22
Nodes (4): check_single_instance_toggle(), main(), If already running, toggle by closing., WorkspaceLayoutsPopup

### Community 15 - "main.rs"
Cohesion: 0.23
Nodes (9): ActivateArgs, ActivateWsArgs, AppFinderArgs, CloseArgs, Command, InfoArgs, MoveArgs, Option (+1 more)

### Community 16 - "String"
Cohesion: 0.27
Nodes (13): From, App, JsonApp, JsonInfo, JsonOutput, JsonOutputRef, JsonSeat, JsonWorkspace (+5 more)

### Community 17 - "NamedHandle"
Cohesion: 0.50
Nodes (3): NamedHandle, NamedHandle<T>, T

## Knowledge Gaps
- **32 isolated node(s):** `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH`, `cos-cli`, `NamedHandle<T>` (+27 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `App` connect `String` to `server.rs`, `AppState`, `find_apps`, `main.rs`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `JsonInfo` connect `String` to `server.rs`, `AppState`, `main.rs`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `BackendResponse` connect `server.rs` to `String`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH` to the rest of the system?**
  _32 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `server.rs` be split into smaller, more focused modules?**
  _Cohesion score 0.12626262626262627 - nodes in this community are weakly interconnected._
- **Should `Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `.event` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._