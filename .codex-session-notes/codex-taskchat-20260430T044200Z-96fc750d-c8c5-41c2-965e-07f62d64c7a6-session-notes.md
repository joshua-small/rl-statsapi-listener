# Codex Session Notes

## Instance

- Instance ID: `codex-taskchat-20260430T044200Z-96fc750d-c8c5-41c2-965e-07f62d64c7a6`
- Runtime anchor: 2026-04-29 21:42:00 PDT -0700
- Runtime anchor UTC: 2026-04-30T04:42:00Z
- Note generated: 2026-05-08
- Repository: `/home/small/rl-statsapi-listener`
- Context limitation: This assistant instance worked from this chat history, local repository state, and command output. It did not inspect external task/chat transcripts beyond the files under `.codex-session-notes/`.
- Timeline note: This note intentionally uses the user-provided last runtime timestamp so the archive sorts chronologically with newer task/chat notes that were created first.

## Task Chat Summary

### Initial StatsAPI Listener Context

- Inspected the original repo state, which initially contained:
  - `listen.py`
  - `obs_rl_statsapi.py`
  - local `.data/` snapshots
  - a local `.venv/`
- Confirmed the folder was not initially a git repository.
- Read the existing listener and OBS script:
  - `listen.py` connected to the StatsAPI socket, decoded JSON frames, printed summaries, and optionally wrote basic OBS text files.
  - `obs_rl_statsapi.py` was an OBS Python script updating named OBS text sources for clock, scores, events, status, and score colors.

### Local Snapshot Data Review

- Reviewed local `.data` files supplied by the user:
  - `.data/player.yml`
  - `.data/club.yml`
  - `.data/club-roster.yml`
  - `.data/freeplay_goal.yml`
  - `.data/dejavu/player_counter.yml`
  - `.data/dejavu/player_counter.json.bak`
  - `.data/obscounter-stats.txt`
- Noted that `.data/club-roster.yml` used a hyphen in the filename, not the underscore form mentioned earlier in the chat.
- Verified the original Dejavu YAML was large, roughly 282k lines.
- Verified the original Dejavu log was very large, roughly 630 MB.
- Confirmed the project had no external YAML dependency installed, so the first implementation stayed standard-library-only.

### SQLite Overlay State Layer

- Added a new SQLite-backed overlay/session state implementation.
- The initial file was `rl_overlay_state.py`; later it was moved into the package as `rl_statsapi_listener/overlay_state.py`.
- Implemented a small YAML-like parser for the simple captured snapshot file shapes.
- Added snapshot import support for:
  - player profile
  - playlist MMR snapshot
  - career stats
  - club info and club stats
  - club roster
  - freeplay goal speed snapshot
  - Dejavu player counters
- Created SQLite tables for:
  - `meta`
  - `profile`
  - `playlist_mmr`
  - `career_stat`
  - `club_info`
  - `club_stat`
  - `club_roster`
  - `players`
  - `player_playlist_records`
  - `matches`
  - `match_players`
  - `shot_speeds`
- Added defensive parsing for StatsAPI payloads where fields may vary by event shape.

### Session And Overlay Outputs

- Added an `OverlayStatsTracker` concept for session state and OBS text outputs.
- Added session tracking for:
  - wins
  - losses
  - current W/L streak
  - low fives
  - high fives
  - demolitions
- Added lifetime stat increments from tracked live deltas where the payload shape exposed them.
- Added MMR display from imported playlist MMR snapshots.
- Added club display text from imported club snapshot data.
- Added Dejavu player display text for known players in the current detected match when IDs, team numbers, playlist, and own team were available.
- Added freeplay shot-speed persistence and outputs:
  - last shot
  - session best
  - all-time best
  - average of last 10

### Listener Integration

- Wired the SQLite-backed tracker into `listen.py`.
- Added CLI flags:
  - `--data-dir`
  - `--stats-db`
  - `--no-overlay-stats`
  - `--reimport-snapshots`
- Kept existing clock/score/event text-file behavior intact.
- Made snapshot import occur on first run or when `--reimport-snapshots` is passed.
- Kept the default database path at `.data/rl_stats.sqlite3`.

### Tests

- Added unit tests for:
  - YAML-like parser handling nested records.
  - snapshot import.
  - session match win updates.
  - session low fives, high fives, and demolitions.
  - lifetime stat increments.
  - Dejavu W/L record updates.
  - MMR text output.
  - freeplay shot speed output.
- The original test file was `test_rl_overlay_state.py`; it was later moved to `tests/test_overlay_state.py`.

### README And Documentation

- Created the first `README.md`.
- Documented:
  - project purpose
  - Rocket League StatsAPI usage
  - OBS plugin-script workflow
  - optional text-file workflow
  - `.data` snapshot files
  - SQLite behavior
  - OBS-generated text files
  - MMR behavior
  - freeplay shot-speed behavior
  - Dejavu record behavior
  - troubleshooting
  - privacy and safety notes
- Added references to:
  - Rocket League StatsAPI
  - RocketStats
  - OBSCounter
  - Deja-Vu
- Documented how the user's personal stats, club roster, and club stats were captured through in-game screenshots, OCR, and cleanup.
- Documented that Dejavu records came from the Deja-Vu BakkesMod plugin data.

### Reference Data And Git Hygiene

- Determined that `.data/obscounter-stats.txt` was reference/planning material rather than personal runtime data.
- Moved it to `docs/reference/obscounter-stats.txt`.
- Added `.gitignore` entries for:
  - `.data/`
  - `.local/`
  - `.venv/`
  - `__pycache__/`
  - Python bytecode
  - SQLite/database files
  - logs
  - local OBS text-output directories
  - `.codex`
  - `.vscode/`
  - `*.code-workspace`
- Removed generated `__pycache__/` files during cleanup.

### Repository Reorganization

- Reorganized the project into a package-oriented structure:
  - `rl_statsapi_listener/cli.py`
  - `rl_statsapi_listener/overlay_state.py`
  - `integrations/obs/obs_rl_statsapi.py`
  - `tests/test_overlay_state.py`
  - `tools/backup_data.py`
  - `docs/reference/obscounter-stats.txt`
- Kept small root compatibility wrappers:
  - `listen.py`
  - `obs_rl_statsapi.py`
- Added `rl_statsapi_listener/__init__.py`.
- Added integration package markers:
  - `integrations/__init__.py`
  - `integrations/obs/__init__.py`
- Added `pyproject.toml` with package metadata and a console script:
  - `rl-statsapi-listen = "rl_statsapi_listener.cli:main"`
- Clarified that the repo name can use hyphens while the importable Python package should use underscores.

### Local Data Backup Tool

- Added `tools/backup_data.py`.
- The tool creates timestamped `.tar.gz` archives of `.data`.
- Default output directory is `.local/backups`.
- `.log` files are skipped by default to avoid huge backups from Deja-Vu logs.
- The tool writes a `MANIFEST.sha256` into the archive.
- Added `--include-logs` for full backups.
- Added `--output-dir` for backups outside the repository.
- Created local backups during the chat, including:
  - `.local/backups/rl-statsapi-data-20260429-171602.tar.gz`
  - `.local/backups/rl-statsapi-data-20260429-173546.tar.gz`

### User Local File Changes Adapted

- User moved `rl-statsapi-listener.code-workspace` from `.data/dejavu` to repo root.
- Confirmed it was a generic VS Code workspace pointing at `.`.
- Added `*.code-workspace` to `.gitignore`.
- User deleted the old `.data/dejavu/` folder, huge `dejavu.log`, and JSON backup.
- User renamed `player_counter.yml` to `.data/dejavu_player_counter.yml`.
- Updated the importer to prefer `.data/dejavu_player_counter.yml`.
- Kept legacy support for `.data/dejavu/player_counter.yml`.
- Updated tests and README references to the new Dejavu file path.

### User Questions Answered

- Explained that SQLite is not a running server like MongoDB; it is a local database file opened by the Python process when needed.
- Explained that `pyproject.toml` belongs at repo root.
- Explained that root `listen.py` and `obs_rl_statsapi.py` are acceptable compatibility/convenience wrappers rather than scripts that need to live under `scripts/`.
- Suggested first commit messages:
  - `Initial RL StatsAPI listener and OBS overlay state`
  - `Initial local RL StatsAPI listener and OBS overlay tooling`

## Verification Run

- Python unit tests passed after initial SQLite-state implementation.
- Python compile checks passed for the listener, OBS script, overlay state, and tests.
- Real `.data` import smoke test pulled in:
  - `28493` player rows
  - `27844` player playlist records
  - `10` MMR rows
  - `19` club roster rows before later user cleanup
- After the later Dejavu rename, current `.data/dejavu_player_counter.yml` import smoke test still pulled in:
  - `28493` players
  - `27844` player playlist records
  - `10` MMR rows
- `listen.py --help` worked after the package reorganization.
- `tools/backup_data.py --help` worked after adding the backup tool.
- `python -m unittest discover -s tests -v` passed with 2 tests during this instance's final verification.

## Important Local State

- `.data/` is ignored personal/runtime data.
- `.local/` is ignored local backup/runtime data.
- `docs/reference/obscounter-stats.txt` is reference material intended to be commit-safe.
- Root `listen.py` is intentionally small because the real CLI implementation lives in `rl_statsapi_listener/cli.py`.
- Root `obs_rl_statsapi.py` is intentionally small because the canonical OBS script lives in `integrations/obs/obs_rl_statsapi.py`.
- Later task/chats may have substantially changed source files beyond the work described here. This note records the work done by this archived instance and the follow-up cleanup performed before archiving.

## Suggested Commit Message From This Task Chat

```text
Initial local StatsAPI listener and OBS overlay tooling

- add SQLite-backed session, lifetime, club, freeplay, and Dejavu state
- import local snapshot data from ignored .data files
- add OBS text-file outputs and preserve the OBS script workflow
- document StatsAPI usage, data provenance, git hygiene, and operation
- organize source, tests, integrations, tools, and reference files for first commit
```
