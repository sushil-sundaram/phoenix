# Graph Report - phoenix  (2026-11-16)

## Corpus Check
- 15 files · ~13,332 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 256 nodes · 498 edges · 15 communities (12 shown, 3 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 8 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0b2646de`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- server.rs
- Commands
- .event
- phoenix_profile.py
- main.rs
- CliError
- rules/graphify.md
- cosmic-session-restorer.py
- workflows/graphify.md
- cosmic-session-restore.sh
- Phoenix: COSMIC Session Restorer & Profile Manager
- cosmic-session-saver.py
- phoenix
- cos-cli
- TaskGuard

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

## Communities (15 total, 3 thin omitted)

### Community 0 - "server.rs"
Cohesion: 0.15
Nodes (28): Arc, ActivateParams, ActivateWsParams, BackendRequest, BackendRequestParams, BackendResponse, CloseParams, internal_error() (+20 more)

### Community 1 - "Commands"
Cohesion: 0.08
Nodes (22): `activate`, `close`, Example: Pin apps to fixed workspaces (Python), `info`, JSON-RPC Server Mode, Methods, `move`, Notifications (+14 more)

### Community 2 - ".event"
Cohesion: 0.14
Nodes (21): Dispatch, Event, QueueHandle, AppState, bind(), AppState, Connection, ExtWorkspaceGroupHandleV1 (+13 more)

### Community 3 - "phoenix_profile.py"
Cohesion: 0.11
Nodes (27): detect_profile(), get_active_wifi_ssids(), get_connected_monitors(), get_env(), get_profile_state(), get_snapshot_paths(), load_profiles_config(), Returns (monitors, models, details) Combines cosmic-randr, cos-cli, and… (+19 more)

### Community 4 - "main.rs"
Cohesion: 0.08
Nodes (42): HashMap, Item, Iterator, ObjectId, ActivateArgs, ActivateWsArgs, App, AppFinderArgs (+34 more)

### Community 5 - "CliError"
Cohesion: 0.15
Nodes (14): Debug, Display, Formatter, From, CliError, discover(), init_tracing(), main() (+6 more)

### Community 7 - "cosmic-session-restorer.py"
Cohesion: 0.29
Nodes (14): app_ids_match(), get_desktop_commands(), get_env(), get_installed_flatpaks(), get_launch_command(), get_live_state(), move_window_and_verify(), Queries cos-cli info --json and returns dynamic output maps and live apps. (+6 more)

### Community 9 - "cosmic-session-restore.sh"
Cohesion: 0.50
Nodes (3): PATH, cosmic-session-restore.sh script, XDG_RUNTIME_DIR

### Community 10 - "Phoenix: COSMIC Session Restorer & Profile Manager"
Cohesion: 0.20
Nodes (9): 1. Ensure Scripts are Executable and Symlinked, 2. Autostart Restorer, 3. Periodic and Shutdown Systemd Services, Architecture, Key Features, Phoenix: COSMIC Session Restorer & Profile Manager, Profile Configuration (`~/.config/cosmic/profiles.json`), Quick CLI Reference (+1 more)

### Community 11 - "cosmic-session-saver.py"
Cohesion: 0.70
Nodes (4): capture_session(), get_env(), main(), save_session()

### Community 12 - "phoenix"
Cohesion: 0.16
Nodes (17): cmd_profile_add(), cmd_profile_detect(), cmd_profile_edit(), cmd_profile_list(), cmd_profile_restore(), cmd_profile_save(), cmd_profile_switch(), cmd_status() (+9 more)

### Community 14 - "TaskGuard"
Cohesion: 0.50
Nodes (3): Drop, JoinHandle, TaskGuard

## Knowledge Gaps
- **31 isolated node(s):** `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH`, `cos-cli`, `NamedHandle<T>` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `App` connect `main.rs` to `server.rs`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Why does `JsonInfo` connect `main.rs` to `server.rs`, `CliError`?**
  _High betweenness centrality (0.045) - this node is a cross-community bridge._
- **Why does `BackendResponse` connect `server.rs` to `main.rs`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **What connects `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `.event` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._
- **Should `phoenix_profile.py` be split into smaller, more focused modules?**
  _Cohesion score 0.10846560846560846 - nodes in this community are weakly interconnected._