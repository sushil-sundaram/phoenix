# Graph Report - phoenix  (2026-11-01)

## Corpus Check
- 12 files · ~10,452 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 208 nodes · 426 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4f53952c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- server.rs
- Commands
- .event
- AppState
- main.rs
- CliError
- rules/graphify.md
- cosmic-session-restorer.py
- workflows/graphify.md
- cosmic-session-restore.sh
- Setup Instructions
- cosmic-session-saver.py
- cos-cli

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

## Communities (13 total, 3 thin omitted)

### Community 0 - "server.rs"
Cohesion: 0.13
Nodes (31): Arc, Drop, JoinHandle, ActivateParams, ActivateWsParams, BackendRequest, BackendRequestParams, BackendResponse (+23 more)

### Community 1 - "Commands"
Cohesion: 0.08
Nodes (22): `activate`, `close`, Example: Pin apps to fixed workspaces (Python), `info`, JSON-RPC Server Mode, Methods, `move`, Notifications (+14 more)

### Community 2 - ".event"
Cohesion: 0.14
Nodes (21): Dispatch, Event, QueueHandle, AppState, bind(), AppState, Connection, ExtWorkspaceGroupHandleV1 (+13 more)

### Community 3 - "AppState"
Cohesion: 0.16
Nodes (14): HashMap, Item, Iterator, ObjectId, AppState, HandleMap, ExtWorkspaceGroupHandleV1, ExtWorkspaceHandleV1 (+6 more)

### Community 4 - "main.rs"
Cohesion: 0.14
Nodes (26): ActivateArgs, ActivateWsArgs, App, AppFinderArgs, CloseArgs, Command, find_apps(), InfoArgs (+18 more)

### Community 5 - "CliError"
Cohesion: 0.12
Nodes (16): Debug, Display, Formatter, From, CliError, discover(), init_tracing(), main() (+8 more)

### Community 7 - "cosmic-session-restorer.py"
Cohesion: 0.29
Nodes (14): app_ids_match(), get_desktop_commands(), get_env(), get_installed_flatpaks(), get_launch_command(), get_live_state(), move_window_and_verify(), Queries cos-cli info --json and returns dynamic output maps and live apps. (+6 more)

### Community 9 - "cosmic-session-restore.sh"
Cohesion: 0.50
Nodes (3): PATH, cosmic-session-restore.sh script, XDG_RUNTIME_DIR

### Community 10 - "Setup Instructions"
Cohesion: 0.22
Nodes (8): 1. Make Scripts Executable, 2. Configure the Autostart Restorer, 3. Configure the Shutdown Saver Service, 4. Enable and Start the Systemd Service, Architecture, Features, Phoenix: COSMIC Session Restorer, Setup Instructions

### Community 11 - "cosmic-session-saver.py"
Cohesion: 0.83
Nodes (3): capture_session(), get_env(), main()

## Knowledge Gaps
- **30 isolated node(s):** `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH`, `cos-cli`, `NamedHandle<T>` (+25 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `App` connect `main.rs` to `server.rs`, `AppState`?**
  _High betweenness centrality (0.107) - this node is a cross-community bridge._
- **Why does `JsonInfo` connect `main.rs` to `server.rs`, `AppState`, `CliError`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Why does `BackendResponse` connect `server.rs` to `main.rs`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **What connects `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `PATH` to the rest of the system?**
  _30 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `server.rs` be split into smaller, more focused modules?**
  _Cohesion score 0.12626262626262627 - nodes in this community are weakly interconnected._
- **Should `Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `.event` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._