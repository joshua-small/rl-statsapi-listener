# Architecture

This repository has one live data source and four supported presentation paths.
The core boundary is between code that talks to Rocket League StatsAPI, code
that persists or transforms overlay state, and host-specific integration code.

## Current State Diagram

```text
Rocket League StatsAPI
  127.0.0.1:49123
        |
        +--> integrations/obs/obs_rl_statsapi.py
        |       -> OBS Text Sources
        |
        +--> listen.py / rl_statsapi_listener.cli
                |
                +--> rl_statsapi_listener.overlay_state
                |       -> .data/rl_stats.sqlite3
                |       -> obs-output/*.txt
                |       -> obs-output/overlay_state.json
                |
                +--> rl_statsapi_listener.web_overlay_server
                        -> http://127.0.0.1:8765/
                        -> /state.json
                        -> /layout.json
                        |
                        +--> OBS Browser Source
                        +--> integrations/windows-webview-host
```

Snapshot imports feed the SQLite-backed path:

```text
.data/player.yml
.data/club.yml
.data/club-roster.yml
.data/freeplay_goal.yml
.data/dejavu_player_counter.yml
        -> rl_statsapi_listener.overlay_state
        -> .data/rl_stats.sqlite3
```

Layout measurements feed only the browser-overlay path:

```text
.data/safezones.yml
.data/scoreboard-layouts.json
        -> /layout.json
        -> rl_statsapi_listener/web_overlay/
```

## Responsibility Map

| Area | Owns | Does not own |
| --- | --- | --- |
| `listen.py` | Backward-compatible CLI entry point. | Listener behavior beyond calling `rl_statsapi_listener.cli.main`. |
| `rl_statsapi_listener/cli.py` | StatsAPI socket loop, console output, latest JSON capture, OBS text-file writing, web-overlay startup. | Persistent stats rules, browser rendering, OBS Python script state. |
| `rl_statsapi_listener/overlay_state.py` | Snapshot import, SQLite schema, live match/session/lifetime stats, Deja-Vu records, freeplay and replay speed state, structured overlay state. | Socket reads, CSS layout, OBS source mutation. |
| `rl_statsapi_listener/web_overlay_server.py` | Static overlay serving, `/state.json`, `/layout.json`, safezone/layout file loading. | Overlay visual decisions beyond serving files and data. |
| `rl_statsapi_listener/web_overlay/` | Browser overlay HTML, CSS, and JavaScript. | Stats aggregation, SQLite, direct StatsAPI socket reads. |
| `integrations/obs/obs_rl_statsapi.py` | OBS Python script workflow that updates named OBS Text Sources directly. | SQLite-backed session/lifetime stats and browser overlay state. |
| `obs_rl_statsapi.py` | Backward-compatible wrapper for the OBS script path. | Canonical OBS integration implementation. |
| `integrations/windows-webview-host/` | Windows transparent, topmost, click-through WebView host for the browser overlay URL. | StatsAPI parsing, overlay state aggregation, browser overlay assets. |
| `tools/backup_data.py` | Local backup archive for ignored `.data` files. | Runtime import or restore automation. |
| `docs/` | Source-controlled contracts, workflow docs, and reference notes. | Personal runtime data. |

## Runtime Contracts

- StatsAPI messages arrive as JSON objects with an `Event` name and event-specific
  `Data`.
- `.data` contains personal local snapshots and generated state; it stays out of
  git. See `docs/data-contracts.md`.
- Browser layout uses `.data/safezones.yml` through `/layout.json`. See
  `docs/web-overlay-layout.md`.
- Media assets used by the browser overlay live under `media/icons/`. See
  `docs/media-assets.md`.
- Test groups and run paths are documented in `tests/README.md`.

## Entry Points

The supported entry points are:

```text
listen.py                  -> rl_statsapi_listener.cli.main
rl-statsapi-listen         -> rl_statsapi_listener.cli:main
obs_rl_statsapi.py         -> integrations.obs.obs_rl_statsapi
integrations/obs/*.py      -> canonical OBS script implementation
```

No entry point is currently deprecated. Keep examples using `listen.py` for
local checkout workflows because it works without package installation. Use the
`rl-statsapi-listen` console script for installed-package workflows. Keep the
root `obs_rl_statsapi.py` wrapper so existing OBS scenes that reference that
file path do not break; make OBS implementation changes under
`integrations/obs/obs_rl_statsapi.py`.

## Where To Change Things

Use this map when choosing a change location:

| Change | Start here |
| --- | --- |
| New CLI flag or socket/debug output | `rl_statsapi_listener/cli.py` |
| New live/session/lifetime stat | `rl_statsapi_listener/overlay_state.py` |
| New generated OBS text file | `rl_statsapi_listener/overlay_state.py` for rich stats, or `rl_statsapi_listener/cli.py` for basic socket-only fields |
| OBS Text Source direct update | `integrations/obs/obs_rl_statsapi.py` |
| Browser overlay placement or rendering | `rl_statsapi_listener/web_overlay/` and `docs/web-overlay-layout.md` |
| Browser feed shape | `overlay_state.py`, `web_overlay_server.py`, and tests that consume `/state.json` or `/layout.json` |
| Windows transparent overlay host behavior | `integrations/windows-webview-host/` |
| `.data` shape, import expectations, or backup notes | `docs/data-contracts.md` and `tools/backup_data.py` |

## Verification Surface

Baseline Python verification:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Browser overlay layout verification:

```bash
npm run test:web
```

Use the browser test path when CSS, overlay placement, icon loading, `/state.json`,
or `/layout.json` behavior changes.
