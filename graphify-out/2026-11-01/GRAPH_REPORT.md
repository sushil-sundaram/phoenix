# Graph Report - phoenix  (2026-09-12)

## Corpus Check
- 10 files · ~9,132 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 194 nodes · 406 edges · 14 communities (13 shown, 1 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `91eb7eb9`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- server.rs
- Commands
- .event
- AppState
- Option
- find_apps
- main.rs
- cosmic-session-restorer.py
- CliError
- cosmic-session-restore.sh
- Phoenix: COSMIC Session Restorer
- cosmic-session-saver.py
- NamedHandle
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

## Communities (14 total, 1 thin omitted)

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
Cohesion: 0.14
Nodes (17): HashMap, Item, Iterator, ObjectId, App, AppState, HandleMap, ExtWorkspaceGroupHandleV1 (+9 more)

### Community 4 - "Option"
Cohesion: 0.18
Nodes (10): ActivateArgs, ActivateWsArgs, AppFinderArgs, CloseArgs, Command, InfoArgs, MoveArgs, Option (+2 more)

### Community 5 - "find_apps"
Cohesion: 0.23
Nodes (13): Display, Formatter, discover(), find_apps(), init_tracing(), main(), Box, Connection (+5 more)

### Community 6 - "main.rs"
Cohesion: 0.49
Nodes (9): JsonApp, JsonInfo, JsonOutput, JsonOutputRef, JsonSeat, JsonWorkspace, JsonWorkspaceGroup, JsonWorkspaceRef (+1 more)

### Community 7 - "cosmic-session-restorer.py"
Cohesion: 0.54
Nodes (7): get_env(), get_launch_command(), get_live_state(), Disables Chrome Profile Picker and resets exit_type so tabs restore…, restore_session(), run_cos_cli(), sanitize_chrome_environment()

### Community 8 - "CliError"
Cohesion: 0.33
Nodes (4): Debug, From, CliError, Self

### Community 9 - "cosmic-session-restore.sh"
Cohesion: 0.40
Nodes (4): PATH, cosmic-session-restore.sh script, WAYLAND_DISPLAY, XDG_RUNTIME_DIR

### Community 10 - "Phoenix: COSMIC Session Restorer"
Cohesion: 0.40
Nodes (4): Architecture, Features, Phoenix: COSMIC Session Restorer, Setup

### Community 11 - "cosmic-session-saver.py"
Cohesion: 0.83
Nodes (3): capture_session(), get_env(), main()

### Community 12 - "NamedHandle"
Cohesion: 0.50
Nodes (3): NamedHandle, NamedHandle<T>, T

## Knowledge Gaps
- **26 isolated node(s):** `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY`, `PATH`, `cos-cli` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `App` connect `AppState` to `server.rs`, `Option`, `find_apps`, `main.rs`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Why does `JsonInfo` connect `main.rs` to `CliError`, `server.rs`, `AppState`, `Option`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `BackendResponse` connect `server.rs` to `main.rs`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **What connects `cosmic-session-restore.sh script`, `XDG_RUNTIME_DIR`, `WAYLAND_DISPLAY` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `server.rs` be split into smaller, more focused modules?**
  _Cohesion score 0.12626262626262627 - nodes in this community are weakly interconnected._
- **Should `Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.08333333333333333 - nodes in this community are weakly interconnected._
- **Should `.event` be split into smaller, more focused modules?**
  _Cohesion score 0.1422924901185771 - nodes in this community are weakly interconnected._