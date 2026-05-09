# RL StatsAPI Listener

A local Rocket League overlay helper. It listens to the local
[Rocket League StatsAPI](https://www.rocketleague.com/en/developer/stats-api),
imports local `.data` snapshots, tracks match/session/lifetime stats in SQLite,
and exposes the results through OBS text files, an OBS Python script, or a
browser overlay.

This project does not inject into Rocket League. It only consumes data exposed
by the local StatsAPI source you already run.

## Quick Start

Enable Rocket League StatsAPI first, then choose one workflow.

### OBS Python Script

Use this for a simple direct OBS text-source setup:

```text
OBS > Tools > Scripts > add obs_rl_statsapi.py
```

Create OBS Text Sources using the names configured in the script settings. The
root `obs_rl_statsapi.py` is a compatibility wrapper; the canonical script is
`integrations/obs/obs_rl_statsapi.py`.

See `docs/integrations/obs-python-script.md`.

### Text Files

Use this for SQLite-backed session/lifetime/freeplay/Deja-Vu values in OBS Text
Sources:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output
```

Then configure OBS Text Sources to read the generated `.txt` files.

See `docs/integrations/text-file-output.md`.

### Browser Overlay

Use this for the built-in transparent HTML/CSS stats panel:

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Open:

```text
http://127.0.0.1:8765/
```

Use that URL in an OBS Browser Source or in the Windows WebView host.

See `docs/integrations/browser-overlay.md`.

### Windows WebView Host

Use this when you want the browser overlay above a borderless/windowed game
without relying on OBS projection:

```powershell
.\integrations\windows-webview-host\Start-OverlayHost.ps1 -Url http://127.0.0.1:8765/ -Monitor 1
```

From WSL:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(wslpath -w integrations/windows-webview-host/Start-OverlayHost.ps1)" -Url http://127.0.0.1:8765/ -Monitor 1
```

The host starts topmost and click-through. Use `Ctrl+Shift+F10` to toggle
click-through, `Ctrl+Shift+F11` to reload, and `Ctrl+Shift+F9` to exit.

See `docs/integrations/windows-webview-host.md`.

## Which Workflow Should I Use?

| Need | Use |
| --- | --- |
| Basic OBS clock, scores, event text, and status with no separate listener process | OBS Python script |
| Many individual OBS Text Sources backed by session/lifetime/freeplay stats | Text-file output |
| One transparent visual overlay in OBS or a browser-like host | Browser overlay |
| Transparent topmost in-game overlay outside OBS projection | Windows WebView host |
| Inspect raw StatsAPI payload shape | `listen.py --pretty --latest-events-dir` |
| Back up personal local snapshots and SQLite state | `tools/backup_data.py` |

## Common Commands

Listener help:

```bash
.venv/bin/python listen.py --help
```

Normal text-file run:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output
```

Browser overlay run:

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Reimport updated manual snapshots:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --reimport-snapshots
```

Capture latest StatsAPI event payloads:

```bash
.venv/bin/python listen.py --pretty --latest-events-dir
```

Replay last-goal speed output:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --replay-last-goal
.venv/bin/python listen.py --obs-dir ./obs-output --replay-goal-player-id 'Epic|account-id|0'
```

Back up `.data`:

```bash
.venv/bin/python tools/backup_data.py
```

## Entry Point Compatibility

No entry point is currently deprecated.

Use `listen.py` for local checkout workflows and examples. Installed package
workflows may use the equivalent `rl-statsapi-listen` console script declared in
`pyproject.toml`; both route to `rl_statsapi_listener.cli:main`.

OBS setups may keep adding the root `obs_rl_statsapi.py` script. It is a thin
compatibility wrapper for `integrations/obs/obs_rl_statsapi.py`, which remains
the canonical file to edit.

## Repository Map

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
│   ├── obs/                          # Canonical OBS Python script
│   └── windows-webview-host/         # Windows transparent WebView host
├── media/icons/                      # Web overlay stat, playlist, and rank icons
├── tests/                            # Python and browser overlay tests
├── tools/                            # Maintenance helpers
├── docs/                             # Architecture, workflow, and contract docs
└── .data/                            # Ignored personal/runtime data
```

Architecture and ownership details live in `docs/architecture.md`.

## Runtime Data

`.data` is personal local data and is excluded from git. It can contain display
names, platform IDs, club roster details, match records, local career stats, and
the generated SQLite database.

Important files:

| Path | Purpose |
| --- | --- |
| `.data/player.yml` | Manual player profile, MMR, career record, and career stats snapshot. |
| `.data/club.yml` | Manual club record and stats snapshot. |
| `.data/club-roster.yml` | Manual club roster snapshot. |
| `.data/freeplay_goal.yml` | Initial freeplay goal speed baseline. |
| `.data/dejavu_player_counter.yml` | Imported Deja-Vu player encounter records. |
| `.data/safezones.yml` | Measured browser overlay safezone rectangles. |
| `.data/scoreboard-layouts.json` | Measured scoreboard layout data for future themes. |
| `.data/rl_stats.sqlite3` | Generated SQLite database. |

The versioned contract for these files is in `docs/data-contracts.md`.

## Documentation

| Doc | Purpose |
| --- | --- |
| `docs/architecture.md` | Current data flow, ownership map, and change locations. |
| `docs/integrations/obs-python-script.md` | Direct OBS Python script workflow. |
| `docs/integrations/text-file-output.md` | Listener-generated OBS text-file workflow. |
| `docs/integrations/browser-overlay.md` | Browser overlay workflow and feeds. |
| `docs/integrations/windows-webview-host.md` | Transparent Windows WebView host workflow. |
| `docs/data-contracts.md` | `.data` inputs/outputs, SQLite ownership, backup/restore workflow. |
| `docs/media-assets.md` | Icon naming convention, rank icon policy, and asset manifest. |
| `docs/web-overlay-layout.md` | Browser overlay safezone and layout feed contract. |
| `tests/README.md` | Test grouping and fast/full run paths. |

## Development

Run the Python tests:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Run the browser-rendering tests for the web overlay:

```bash
npm install
npx playwright install chromium
npm run test:web
```

Compile-check the Python files:

```bash
.venv/bin/python -m py_compile listen.py obs_rl_statsapi.py rl_statsapi_listener/cli.py rl_statsapi_listener/overlay_state.py rl_statsapi_listener/web_overlay_server.py integrations/obs/obs_rl_statsapi.py tests/test_overlay_state.py tools/backup_data.py
```

The Python listener uses only the Python standard library. The Windows host uses
.NET 8 and WebView2.

## Troubleshooting

If the listener cannot connect, confirm Rocket League StatsAPI is enabled and
listening on `127.0.0.1:49123`.

If OBS text files are not changing, confirm `--obs-dir` points to the same
directory OBS reads and that the listener is still connected.

If the browser overlay is blank or stale, check:

```bash
curl http://127.0.0.1:8765/state.json
curl http://127.0.0.1:8765/layout.json
```

If session counters are not moving, run with `--pretty` and inspect whether
StatsAPI is sending the relevant player stat fields. Live Match values can move
before Session values; Session and lifetime counters roll forward only after a
winner-bearing `MatchEnded`.

## Privacy And Safety

Keep `.data`, `.local`, SQLite databases, and generated build output out of git.
At minimum, preserve ignore rules like:

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

Avoid this unless you have a backup:

```bash
git clean -xdf
```

That command can delete ignored files such as `.data/`, `.venv/`, and `.local/`.

## Reference Projects

- [Rocket League StatsAPI](https://www.rocketleague.com/en/developer/stats-api):
  official local gameplay/event data source.
- [RocketStats](https://github.com/Lyliya/RocketStats): prior art for session
  info such as MMR, wins, losses, and streaks in-game and in OBS.
- [OBSCounter](https://github.com/ubelhj/OBSCounter): prior art for Rocket
  League stat counters and OBS file output.
- [Deja-Vu](https://github.com/adamk33n3r/Deja-Vu): prior art/source data for
  tracking players you have played with or against.
