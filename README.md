# RL StatsAPI Listener

A small local Rocket League overlay helper. It listens to the local [Rocket League StatsAPI](https://www.rocketleague.com/en/developer/stats-api), keeps session/lifetime stats in SQLite, imports manually captured career/club/player data from `.data`, and can write simple text files that OBS can display.

This does not inject into Rocket League. It only consumes data exposed by the local StatsAPI source you already run.

The long-term goal is to recover a lot of the useful overlay/stat-management behavior from projects like [RocketStats](https://github.com/Lyliya/RocketStats), [OBSCounter](https://github.com/ubelhj/OBSCounter), and [Deja-Vu](https://github.com/adamk33n3r/Deja-Vu), but using the official StatsAPI and local persisted state where possible.

## Quick Start

From the repo root:

Current OBS plugin-script workflow:

```text
OBS > Tools > Scripts > add obs_rl_statsapi.py
```

Then create OBS Text Sources with the names configured in the script settings. Start Rocket League with StatsAPI enabled, and the script updates those sources directly.

The root `obs_rl_statsapi.py` file is a compatibility wrapper. The canonical script source lives at `integrations/obs/obs_rl_statsapi.py`.

Optional text-file workflow:

```bash
.venv/bin/python listen.py --obs-dir /path/to/obs-text-files
```

Browser overlay workflow:

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Then open `http://127.0.0.1:8765/`.

Use that URL directly in an OBS Browser Source, or point a Windows transparent/click-through window host at the same URL when you want the overlay above a borderless game window without relying on OBS projection. The page uses a transparent background, so the compositor/window host is responsible for preserving top-level window transparency.

Windows transparent overlay host:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 -Url http://127.0.0.1:8765/ -Monitor 1
```

The host starts topmost and click-through. Use `Ctrl+Shift+F10` to toggle click-through, `Ctrl+Shift+F11` to reload, and `Ctrl+Shift+F9` to exit.

If you are in VS Code Remote/WSL, run the Python listener in WSL and launch the Windows host through Windows PowerShell:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w integrations/windows-webview-host/Start-OverlayHost.ps1)" -Url http://127.0.0.1:8765/ -Monitor 1
```

The listener will:

- Connect to `127.0.0.1:49123`.
- Import snapshot data from `.data` the first time it runs.
- Create/update `.data/rl_stats.sqlite3`.
- Write OBS-friendly `.txt` files into `--obs-dir`.
- Optionally serve an HTML/CSS/JS overlay plus `state.json` and `layout.json` feeds with `--web-overlay`.
- Keep listening until you stop it with `Ctrl+C`.

If you manually edit or replace the `.data/*.yml` snapshot files later, run:

```bash
.venv/bin/python listen.py --obs-dir /path/to/obs-text-files --reimport-snapshots
```

## Folder Structure

```text
.
├── listen.py                         # Compatibility wrapper for the CLI
├── obs_rl_statsapi.py                # Compatibility wrapper for the OBS script
├── pyproject.toml                    # Package metadata and console script config
├── rl_statsapi_listener/
│   ├── cli.py                        # Main StatsAPI socket listener
│   ├── overlay_state.py              # SQLite/import/session tracking logic
│   ├── web_overlay_server.py         # Local HTTP server for browser overlays
│   └── web_overlay/                  # Browser overlay HTML/CSS/JS
├── integrations/
│   ├── windows-webview-host/         # Windows transparent/click-through WebView host
│   └── obs/
│       └── obs_rl_statsapi.py        # Canonical OBS Python script
├── media/
│   └── icons/                        # Web overlay stat, playlist, and rank icons
├── package.json                      # Playwright browser-rendering test tooling
├── playwright.config.js              # Web overlay screenshot/layout test config
├── tests/
│   └── test_*.py                     # Unit tests
├── tools/
│   └── backup_data.py                # Local .data backup helper
├── docs/
│   ├── web-overlay-layout.md         # Browser overlay safezone/layout notes
│   └── reference/
│       └── obscounter-stats.txt      # OBSCounter datapoint reference list
└── .data/                            # Ignored personal/runtime data
```

Why this shape:

- Reusable app logic lives in the `rl_statsapi_listener` package.
- OBS-specific code lives under `integrations/obs`.
- Tests live under `tests`.
- Maintenance scripts live under `tools`.
- Personal runtime data stays in `.data`, outside git.
- Tiny root wrappers keep your existing commands and OBS script path working.

## What Each Part Does

### Rocket League StatsAPI

The official Rocket League StatsAPI is the live data source for this project.

What it provides:

- A local socket on the player's machine.
- JSON messages with an `Event` name and event-specific `Data`.
- Periodic `UpdateState` packets when enabled.
- Match events such as `GoalScored`, `MatchEnded`, `ClockUpdatedSeconds`, `BallHit`, and `StatfeedEvent`.
- Default local port `49123`.

Why it matters:

- It is the safe, official source for live match data.
- It can power broadcaster HUDs and local overlay tools.
- It avoids memory reading, injection, or BakkesMod-only hooks.

Important setup note:

- StatsAPI has to be enabled in Rocket League's `DefaultStatsAPI.ini` before launching the game. Config changes made while Rocket League is already running require a restart.

### `listen.py` And `rl_statsapi_listener/cli.py`

The command-line listener.

`listen.py` is a tiny wrapper. The implementation lives in `rl_statsapi_listener/cli.py`.

It opens a connection to the StatsAPI stream, decodes incoming JSON messages, prints either summaries or pretty JSON, optionally writes the basic clock/score/event OBS files, and passes every event into the stats tracker.

Why it is here:

- This is the main process for the newer SQLite-backed/session-tracking path.
- It is intentionally boring: connect, parse, update files.
- OBS can read plain text files if the plugin-script approach gets awkward or if a datapoint is easier to expose through files.

Useful flags:

```bash
.venv/bin/python listen.py --help
.venv/bin/python listen.py --pretty
.venv/bin/python listen.py --raw-chunks
.venv/bin/python listen.py --quiet
.venv/bin/python listen.py --obs-dir ./obs-output
.venv/bin/python listen.py --obs-dir ./obs-output --replay-last-goal
.venv/bin/python listen.py --obs-dir ./obs-output --replay-goal-player-id 'Epic|account-id|0'
.venv/bin/python listen.py --latest-frame-json
.venv/bin/python listen.py --latest-events-json
.venv/bin/python listen.py --latest-events-dir
.venv/bin/python listen.py --stats-db .data/rl_stats.sqlite3
.venv/bin/python listen.py --data-dir .data
.venv/bin/python listen.py --reimport-snapshots
.venv/bin/python listen.py --no-overlay-stats
.venv/bin/python listen.py --web-overlay --web-port 8766
```

### `rl_statsapi_listener/overlay_state.py`

The persistence and overlay stats brain.

It imports the YAML-ish snapshot files, creates the SQLite schema, tracks current match/session state, updates lifetime counters after completed winner-bearing matches, records freeplay shot speeds, writes the richer overlay text files, and exposes structured state for the browser overlay.

Why it is here:

- Session stats reset each run, but lifetime-ish stats need durable storage.
- SQLite gives you a single local database without needing a server.
- The app can start from manually captured stats, then increment them while it runs.
- Dejavu/player records need structured storage if you want mode-by-mode W/L later.

Main things it stores:

- Player profile and MMR snapshots.
- Career stats such as wins, low fives, high fives, demolitions, and deaths.
- Club info, club stats, and club roster.
- Player records, including `with` and `against` records per playlist.
- Completed matches, so the same match does not double-count.
- Freeplay shot speeds.

### `obs_rl_statsapi.py` And `integrations/obs/obs_rl_statsapi.py`

The current OBS plugin-script workflow.

The root `obs_rl_statsapi.py` is a compatibility wrapper. The canonical script lives at `integrations/obs/obs_rl_statsapi.py`.

It connects directly from OBS to StatsAPI and updates OBS text sources by name for clock, scores, event text, status, and team score colors.

Why it is here:

- This is what you have actually been using so far.
- It lets OBS talk to StatsAPI directly.
- The user creates OBS Text Sources for each datapoint in the script and names them accordingly.
- Good for a simple scoreboard-style overlay.
- Avoids needing OBS to watch a directory of text files.

Current caveat:

- The richer SQLite-backed session/lifetime/Dejavu/freeplay tracking lives in `listen.py` + `rl_statsapi_listener/overlay_state.py`, not in this OBS script yet.
- The long-term version may either extend this OBS script with more datapoints, use generated text files, or support both.

### Browser Overlay

`--web-overlay` starts a local HTTP server from inside the listener.

What it serves:

- `http://127.0.0.1:8765/` for the transparent overlay page.
- `http://127.0.0.1:8765/state.json` for the live structured state.
- `http://127.0.0.1:8765/layout.json` for local safezone and scoreboard layout data loaded from `--data-dir`.

Why it is useful:

- OBS can consume it as a normal Browser Source.
- A Windows transparent-window wrapper can consume the same URL for a topmost, click-through in-game overlay.
- The visual layout lives in regular HTML/CSS/JavaScript under `rl_statsapi_listener/web_overlay/`.
- The data contract stays local and simple, so future overlay hosts do not need to know about SQLite or StatsAPI message shapes.

Current layout behavior:

- The browser overlay renders a taller in-match/freeplay stats panel and a compact two-row menu strip.
- The in-match/freeplay panel is positioned and clipped to `.data/safezones.yml` at `match.stats`.
- The in-match/freeplay panel shows live Match stats, completed-session totals, per-completed-game averages, Deaths, KD, and your latest goal speed.
- The menu strip is positioned and clipped to `.data/safezones.yml` at `menu.stats`.
- The built-in fallback rectangles are `match.stats={w:422,h:447,x:0,y:802}` and `menu.stats={w:684,h:102,x:1192,y:1238}` on a `2560x1440` reference canvas.
- Stat icons are served from `/media/icons/stats/*.webp`.
- `.data/scoreboard-layouts.json` is exposed through `layout.json` for future scoreboard/theme work, but match conditions and series wins are not rendered yet.
- The measured safezone coordinates currently assume a `2560x1440` reference resolution and scale to the browser viewport.

See `docs/web-overlay-layout.md` for the layout file contract and current theme limitations.

### Windows WebView Host

`integrations/windows-webview-host/` contains a Windows-only .NET/WPF WebView2 host for the browser overlay.

Why it is here:

- OBS cannot reliably project transparent browser content above every borderless game window.
- The host creates a topmost transparent desktop window and points it at the same local overlay URL.
- It starts click-through/no-activate so Rocket League keeps receiving mouse input.
- It uses global hotkeys for control: `Ctrl+Shift+F10` toggles click-through, `Ctrl+Shift+F11` reloads, and `Ctrl+Shift+F9` exits.

Run it after starting `listen.py --web-overlay`:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 -Url http://127.0.0.1:8765/ -Monitor 1
```

See `integrations/windows-webview-host/README.md` for publish commands, custom bounds, and debugging flags.

### `tests/test_overlay_state.py`

Unit tests for the local stats layer.

It checks the small YAML parser, imports sample snapshot data, simulates a match, verifies session counters, verifies lifetime increments, verifies player W/L updates, and checks OBS text output.

Why it is here:

- The importer and counters are easy to accidentally break.
- The tests make sure the SQLite layer and overlay text files keep behaving while the app evolves.

Run tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

### `tools/backup_data.py`

Backs up your ignored local `.data` directory into a timestamped `.tar.gz` archive.

Why it is here:

- `.data` is intentionally not committed.
- Ignored files survive normal commits and branch switches, but they are still just files on disk.
- A local backup lets you refactor or publish the repo without worrying about losing OCR cleanup work or live stat state.

Default backup:

```bash
.venv/bin/python tools/backup_data.py
```

That writes to `.local/backups/` and skips `.log` files by default so the archive does not balloon because of huge Deja-Vu logs.

Include logs too:

```bash
.venv/bin/python tools/backup_data.py --include-logs
```

Back up outside the repo:

```bash
.venv/bin/python tools/backup_data.py --output-dir ~/rl-statsapi-listener-backups
```

### `.data/`

Local captured data and generated state.

This directory is the bridge between data you captured manually and the live tracker. Treat it as personal data.

Important files:

- `.data/player.yml`: Your manually captured player profile, MMR snapshot, career record, and career stats.
- `.data/club.yml`: Your manually captured club record and club stats.
- `.data/club-roster.yml`: Your manually captured club roster.
- `.data/freeplay_goal.yml`: A sample/manual freeplay goal speed snapshot.
- `.data/dejavu_player_counter.yml`: Historical player encounter records from Deja-Vu.
- `.data/safezones.yml`: Manually measured UI-safe rectangles for overlay surfaces. The browser overlay uses `match.stats` for match/freeplay and `menu.stats` for menu.
- `.data/scoreboard-layouts.json`: Manually measured scoreboard element/layout coordinates for future broadcaster-style themes.
- `.data/schemas/scoreboard-layouts.schema.json`: Draft schema/reference for the scoreboard layout capture data.
- `.data/rl_stats.sqlite3`: Generated SQLite database. This appears after running the listener with overlay stats enabled.

Why it is here:

- Some Rocket League career data is not currently available live.
- Manual snapshots give the app a baseline.
- SQLite then moves forward from that baseline while the app is running.

Where the data came from:

- `player.yml` came from screenshots of Main Menu > Profile > Career > Stats, then OCR, cleanup, and manual structuring.
- `club-roster.yml` came from screenshots of Main Menu > Club > Show Roster, then OCR and cleanup.
- `club.yml` came from screenshots of Main Menu > Club > Stats, then OCR and cleanup.
- `dejavu_player_counter.yml` came from the Deja-Vu BakkesMod plugin data, with `player_counter` cleaned up afterward.
- `safezones.yml` and `scoreboard-layouts.json` came from screenshot analysis and Photoshop measurements. The current safezone scaler uses a `2560x1440` reference resolution.

Git note:

- `.data` is personal local data and is excluded from git by `.gitignore`.
- Generated SQLite files should also stay out of git.
- If sample data is useful later, create sanitized fixtures under a separate test/sample directory instead of committing your real `.data`.

### `docs/`

Source-controlled project notes and reference material that are useful for planning but are not personal runtime data.

Important files:

- `docs/web-overlay-layout.md`: Notes for `.data/safezones.yml`, `.data/scoreboard-layouts.json`, and the current browser overlay layout contract.
- `docs/reference/obscounter-stats.txt`: Placeholder/reference list of all the datapoints OBSCounter exposed.

Why it is here:

- The browser overlay uses personal `.data` measurements at runtime, but the expected shape and current behavior should be documented in git.
- OBSCounter exposed a huge list of useful datapoints.
- These files are maps for future overlay fields and themes.
- They are not user-specific, so they should live outside `.data` and can be committed.

## Data Flow

Current OBS script path:

```text
StatsAPI socket
    -> obs_rl_statsapi.py inside OBS
    -> named OBS Text Sources
```

SQLite/text-file path:

```text
StatsAPI socket
    -> listen.py
    -> rl_statsapi_listener/overlay_state.py
    -> .data/rl_stats.sqlite3
    -> OBS text files
    -> OBS text sources
```

Browser/WebView overlay path:

```text
StatsAPI socket
    -> listen.py --web-overlay
    -> rl_statsapi_listener/overlay_state.py
    -> local /state.json feed
    -> rl_statsapi_listener/web_overlay/
    -> OBS Browser Source or Windows WebView host
```

Snapshot imports happen like this:

```text
.data/player.yml
.data/club.yml
.data/club-roster.yml
.data/freeplay_goal.yml
.data/dejavu_player_counter.yml
    -> rl_statsapi_listener/overlay_state.py
    -> .data/rl_stats.sqlite3
```

## OBS Setup

There are two possible OBS approaches in this repo.

### Option A: OBS Plugin Script

This is the workflow you have been using.

1. Add `obs_rl_statsapi.py` as an OBS Python script. You can also point OBS at `integrations/obs/obs_rl_statsapi.py` directly.
2. Create OBS Text Sources for the datapoints the script supports.
3. Name the Text Sources exactly like the configured source names in the script settings.
4. Start Rocket League with StatsAPI enabled.
5. Let the script connect and update those sources directly.

Use this when:

- You want OBS to receive values directly.
- You do not want a folder full of generated text files.
- The datapoint is already implemented in `obs_rl_statsapi.py`.

### Option B: Text Files

This is the newer path exposed by `listen.py`.

1. Pick or create an output directory, for example:

   ```bash
   mkdir -p ./obs-output
   ```

2. Run the listener:

   ```bash
   .venv/bin/python listen.py --obs-dir ./obs-output
   ```

   To also write the latest replay/match goal speed, enable the replay last-goal output:

   ```bash
   .venv/bin/python listen.py --obs-dir ./obs-output --replay-last-goal
   ```

3. In OBS, add Text sources.

4. For each Text source, enable reading from a file and point it at one of the generated `.txt` files.

Use this when:

- You want the SQLite-backed session/lifetime/freeplay/Dejavu values.
- You want to test new datapoints without changing the OBS plugin script yet.
- A plain file handoff is easier than OBS script state.

Useful generated files:

| File | What it shows |
| --- | --- |
| `clock.txt` | In-match clock |
| `score_blue.txt` | Blue team score |
| `score_orange.txt` | Orange team score |
| `event_name.txt` | Last StatsAPI event name |
| `event_banner.txt` | Simple goal/match event text |
| `session_wins.txt` | Wins since this listener started |
| `session_losses.txt` | Losses since this listener started |
| `session_streak.txt` | Current session streak, like `W3` or `L2` |
| `session_low_fives.txt` | Low fives this session |
| `session_high_fives.txt` | High fives this session |
| `session_demos.txt` | Demolitions this session |
| `session_deaths.txt` | Deaths this session |
| `recent_mmr.txt` | Current playlist's stored MMR snapshot |
| `lifetime_low_fives.txt` | Stored lifetime low fives |
| `lifetime_high_fives.txt` | Stored lifetime high fives |
| `lifetime_demos.txt` | Stored lifetime demolitions |
| `lifetime_deaths.txt` | Stored lifetime deaths |
| `last_goal_speed.txt` | Your latest tracked goal speed |
| `freeplay_last_shot.txt` | Last tracked freeplay shot speed |
| `freeplay_session_best.txt` | Best tracked freeplay shot this listener run |
| `freeplay_all_time_best.txt` | Best stored freeplay shot speed |
| `freeplay_avg_last_10.txt` | Average of last 10 stored shot speeds |
| `replay_last_goal.txt` | Latest replay/match goal speed when `--replay-last-goal` is enabled |
| `club_name.txt` | Club tag/name |
| `club_record.txt` | Compact club record summary |
| `dejavu_players.txt` | Known players in current match, if detected |
| `overlay_state.json` | Structured state used by browser-style overlays |

Optional StatsAPI JSON capture flags:

| Flag | What it writes |
| --- | --- |
| `--latest-frame-json [PATH]` | Latest decoded StatsAPI message as pretty JSON |
| `--latest-events-json [PATH]` | Latest decoded message per tracked event type in one JSON file |
| `--latest-events-dir [DIR]` | One pretty JSON file per tracked event type |

When a path is omitted, these write under `--obs-dir` when provided, otherwise under `--data-dir`.

### Option C: Browser Source Or WebView

This is the shared HTML/CSS/JavaScript overlay path.

1. Run the listener with the web overlay enabled:

   ```bash
   .venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
   ```

2. Check the state feed:

   ```bash
   curl http://127.0.0.1:8765/state.json
   ```

3. Check the layout feed if you are tuning safe zones:

   ```bash
   curl http://127.0.0.1:8765/layout.json
   ```

4. Use `http://127.0.0.1:8765/` as an OBS Browser Source, or point the Windows WebView host at that URL.

Use this when:

- You want one overlay layout that works in OBS and in a Windows transparent window.
- You want the richer SQLite-backed values without making many individual OBS Text Sources.
- You want to iterate on layout with regular HTML/CSS/JavaScript.
- You want the stats panel constrained to the measured stats safezones.

## Operating Notes

### Normal Session

Start the StatsAPI source first, then run:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output
```

Leave that terminal open while you play. Stop with `Ctrl+C` when done.

### First Run

On first run, the app imports `.data` into `.data/rl_stats.sqlite3`. The Dejavu file is large, so the first import can take a little bit. Later runs use the SQLite database directly.

### Manual Snapshot Updates

If the app was not running and your in-game lifetime stats changed, manually update the snapshot file, then reimport:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --reimport-snapshots
```

The importer prefers larger numeric snapshot values for career and club stats, so reimporting a newer manual capture should move those totals forward.

### Keeping Personal Data Safe

Your personal data is preserved locally because `.data/` is ignored by git. Normal commits, pushes, and branch switches do not upload or delete ignored files.

Use this before big refactors, first publish, or any risky cleanup:

```bash
.venv/bin/python tools/backup_data.py
```

That creates a timestamped archive like:

```text
.local/backups/rl-statsapi-data-YYYYMMDD-HHMMSS.tar.gz
```

For a backup that survives deleting this repo folder, put it somewhere outside the repo:

```bash
.venv/bin/python tools/backup_data.py --output-dir ~/rl-statsapi-listener-backups
```

Avoid this unless you have a backup:

```bash
git clean -xdf
```

That command can delete ignored files such as `.data/`, `.venv/`, and `.local/`.

### MMR

Right now, MMR comes from `.data/player.yml` and is stored in the `playlist_mmr` table. `recent_mmr.txt` shows the stored MMR for the most recently detected playlist.

Future options:

- Use Psyonix if they expose MMR in StatsAPI.
- Add a provider for tracker.gg or another legitimate third-party source.
- Keep the provider isolated so the overlay does not care where MMR came from.

### Freeplay Shot Speeds

The app imports `.data/freeplay_goal.yml` as the initial all-time shot speed baseline. During live use, it records shot speed events when StatsAPI sends a recognizable freeplay goal payload with speed fields such as `goalSpeed`, `ShotSpeed`, `BallSpeed`, or `PostHitSpeed`. If Freeplay sends only `UpdateState` frames, the overlay also counts a goal when the Freeplay team score increases and uses the best recent `Game.Ball.Speed` value as the goal speed. If no positive ball speed is available, the goal still counts and the previous last-goal speed remains unchanged.

If freeplay speed files do not update, run:

```bash
.venv/bin/python listen.py --pretty --latest-events-dir
```

Then score a freeplay goal and inspect the event shape plus the JSON files under `.data/latest_statsapi_events/`. The tracker may need another field name added.

### Replay Last Goal Speed

`--replay-last-goal` writes `replay_last_goal.txt` for OBS text sources. It first looks for explicit `GoalScored` or `BallHit` speed fields such as `goalSpeed`, `ShotSpeed`, `BallSpeed`, or `PostHitSpeed`.

Some replay playback only emits `UpdateState` packets. In that case, the listener keeps a short rolling window of `Game.Ball.Speed` values and writes the best recent speed when either team's score increases.

Useful commands:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --replay-last-goal
.venv/bin/python listen.py --obs-dir ./obs-output --replay-goal-player-id 'Epic|account-id|0'
```

Start or restart the listener before replaying the goal sequence so it can see the ball-speed frames before the scoreboard changes. If `replay_last_goal.txt` stays at `-- kph`, run with `--pretty` briefly and inspect whether the replay payload includes `Game.Ball.Speed`, score changes, or a different speed field.

### Dejavu Player Records

The app imports `.data/dejavu_player_counter.yml` into SQLite. That source data came from the [Deja-Vu](https://github.com/adamk33n3r/Deja-Vu) BakkesMod plugin's player tracking data. During matches, if StatsAPI provides player IDs, teams, playlist ID, and match result, this app can increment `with` or `against` records per playlist.

This depends heavily on what the live StatsAPI payload includes. If `dejavu_players.txt` is blank, the most likely cause is missing player IDs, missing team numbers, missing playlist IDs, or the current packet shape needing another parser case.

## Inspecting SQLite

The generated database lives at:

```text
.data/rl_stats.sqlite3
```

Quick examples:

```bash
sqlite3 .data/rl_stats.sqlite3 ".tables"
sqlite3 .data/rl_stats.sqlite3 "select playlist_id, name, value from playlist_mmr order by playlist_id;"
sqlite3 .data/rl_stats.sqlite3 "select name, value_num from career_stat order by name;"
sqlite3 .data/rl_stats.sqlite3 "select count(*) from players;"
```

If `sqlite3` is not installed, the app still works; that command is only for manual inspection.

## Troubleshooting

### `Connection refused`

StatsAPI is not listening at the configured host/port.

Try:

```bash
.venv/bin/python listen.py --host 127.0.0.1 --port 49123
```

Also make sure the StatsAPI source is running before the listener starts.

### OBS files are not changing

Check that:

- You passed `--obs-dir`.
- OBS is reading the same directory.
- The listener terminal says it connected.
- You are looking at text files that are actually generated by this app.

### Browser overlay is blank or not updating

First check whether the state feed is alive:

```bash
curl http://127.0.0.1:8765/state.json
```

From WSL, you can also check from the Windows side:

```bash
powershell.exe -NoProfile -Command "(Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/state.json).Content"
```

If the request fails, restart the listener with `--web-overlay`. If it returns JSON but the window is stale, press `Ctrl+Shift+F11` in the WebView host to reload.

If Windows cannot reach the WSL listener on `127.0.0.1`, start the listener with `--web-host 0.0.0.0`, get the WSL IP with `hostname -I`, then pass `http://<wsl-ip>:8765/` to OBS or the WebView host.

### Session counters are not moving

Run with `--pretty` and inspect whether StatsAPI is sending your player stats in the current event payload:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --pretty
```

The current tracker looks for stat fields like `gameLowFives`, `gameHighFives`, `gameDemolitions`, and `Demos`. Deaths are tracked from your own `bDemolished` false-to-true transitions. Live values move the Match column immediately; Session and lifetime counters move only after `MatchEnded` includes a real winning team.

### Lifetime stats are wrong

If the app missed sessions because it was not running, update `.data/player.yml` from a new manual capture and rerun with `--reimport-snapshots`.

### Dejavu records are not updating

The app needs enough live match data to know:

- Who you are.
- Who else is in the match.
- Which team each player is on.
- Which playlist/mode the match is.
- Which team won.

Use `--pretty` to inspect whether those fields are present.

## TODO / Ideas

Future exploration notes, not committed behavior:

- Add overlay themes for different visual styles and stream/game contexts.
- Add a ticker or slideshow mode for some stat trackers, with recent match events able to temporarily take priority as the currently displayed stat.
- Expand safe zone data by resolution, display mode, and game screen so overlays avoid covering important UI such as boost, scoreboard, menus, or lobby controls.
- Add an input listener for controller, gamepad, or keypress controls to show/hide some or all overlay elements.
- Make the overlay react to whether Rocket League is in a match, lobby, menu, or another screen, since each context has different safe zones and different useful/annoying stats.
- Consider a database compressor or pruning/archival flow if imported data such as Deja-Vu records gets too large.
- Add first-class support for multiple accounts owned by the same user, including per-account views and summed cross-account stats.
- Create an easier install, package, and release path so other users can eventually run this without hand-wiring the repo.
- Clean up and refine the SQLite schemas once the data model has settled more.

## Development

Run tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Run the browser-rendering tests for the web overlay:

```bash
npm install
npx playwright install chromium
npm run test:web
```

These Playwright tests serve deterministic overlay state locally, assert match/freeplay `match.stats` versus menu `menu.stats` placement in Chromium, verify icons load, and save screenshots under `test-results/playwright/`.

Compile-check the Python files:

```bash
.venv/bin/python -m py_compile listen.py obs_rl_statsapi.py rl_statsapi_listener/cli.py rl_statsapi_listener/overlay_state.py rl_statsapi_listener/web_overlay_server.py integrations/obs/obs_rl_statsapi.py tests/test_overlay_state.py tools/backup_data.py
```

Build the Windows WebView host from WSL:

```bash
powershell.exe -NoProfile -Command "dotnet build \"$(wslpath -w integrations/windows-webview-host/RlStatsApiOverlay.Host.csproj)\""
```

The Python listener uses only the Python standard library. The Windows host uses .NET 8 and WebView2.

## Privacy And Safety

The `.data` files and SQLite database can include player names, platform IDs, club roster info, and your own stats. Be careful before sharing them publicly.

This repo has a `.gitignore` for the local/personal pieces. At minimum, keep rules like:

```gitignore
.data/
.local/
*.sqlite3
*.sqlite
*.db
bin/
obj/
*.code-workspace
```

This project is designed around locally exposed StatsAPI data and local files. It does not modify Rocket League memory, inject into the game, or try to work around EAC.

## Reference Projects

- [Rocket League StatsAPI](https://www.rocketleague.com/en/developer/stats-api): Official local gameplay/event data source.
- [RocketStats](https://github.com/Lyliya/RocketStats): Prior art for session info such as MMR, wins, losses, and streaks in-game and in OBS.
- [OBSCounter](https://github.com/ubelhj/OBSCounter): Prior art for counting Rocket League stats and outputting values to files for OBS or an in-game overlay.
- [Deja-Vu](https://github.com/adamk33n3r/Deja-Vu): Prior art/source data for tracking players you have played with or against.
