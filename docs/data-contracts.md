# Data Directory Contracts

Contract version: `data-contracts-v1`

This page documents the source-controlled expectations for local `.data` inputs,
generated outputs, and backup/restore workflows. The directory itself is
personal runtime data and stays ignored by git.

## Path Rules

- `--data-dir` defaults to `.data` and is the source for manual snapshots and
  browser overlay layout measurements.
- `--stats-db` defaults to `.data/rl_stats.sqlite3`. It may point outside
  `--data-dir`, but the importer still reads snapshots from `--data-dir`.
- `--latest-frame-json`, `--latest-events-json`, and `--latest-events-dir`
  default to `--obs-dir` when it is provided. Without `--obs-dir`, they write
  under `--data-dir`.
- Missing snapshot files are allowed. Importers skip missing files and keep the
  database usable.

## Snapshot Input Contract

`data-contracts-v1` is a documentation version, not an in-file field. Current
snapshot files do not need a `contractVersion` key. If a future change requires
renaming required keys or changing units, create a new contract version here and
keep the importer backward compatible until the old shape is deliberately
retired.

The YAML snapshot parser supports the simple shapes used by the captured files:
mappings, lists, comments, quoted or unquoted strings, booleans, null values,
integers, and floats. It is not a full YAML implementation.

| File | Expected shape | Import behavior |
| --- | --- | --- |
| `player.yml` | Mapping with optional `datetime`, `profile`, `MMR`, `Stats`, and `Career Record`. `profile.platformId` and `profile.displayName` identify the local player. `MMR` rows should include `playlistId`, `name`, and `value`. | Updates `profile`, `playlist_mmr`, and flattened `career_stat` rows. Numeric career values prefer larger values on reimport. |
| `club.yml` | Mapping with optional `datetime`, `Club Name`, `Club Tag`, `Club Stats`, and `Club Record`. | Updates `club_info` and flattened `club_stat` rows. Numeric club values prefer larger values on reimport. |
| `club-roster.yml` | Mapping with `roster` list. Each member should include `platform` and `platformId`; `displayName` is optional. | Upserts `club_roster` rows keyed by platform and platform ID. |
| `freeplay_goal.yml` | Mapping with numeric `goalSpeed`; `timestamp` is optional. | Seeds `shot_speeds` as `snapshot:freeplay_goal.yml`. The stored value is treated as kph. |
| `dejavu_player_counter.yml` | Mapping with `players` list. Each player should include `uniqueId`; optional `name`, `metCount`, `timeMet`, `updatedAt`, and per-playlist `records.with` / `records.against` wins and losses. | Upserts `players` and `player_playlist_records`. |
| `dejavu/player_counter.yml` | Legacy path with the same YAML shape as `dejavu_player_counter.yml`. | Used only when the root `dejavu_player_counter.yml` file is absent. |
| `dejavu/player_counter.json.bak` | Legacy JSON fallback with top-level `players` object keyed by unique ID and per-player `playlistData`. | Used only when neither YAML Deja-Vu source exists. |

Snapshot import runs on first database initialization, then records
`meta.snapshots_imported_at`. Use `--reimport-snapshots` after manually updating
snapshot files. Reimport is additive for live SQLite state: it refreshes imported
baselines, while completed match/session increments remain in the database.

## Layout Input Contract

These files are also read from `--data-dir`, but they are not imported into
SQLite.

| File | Expected shape | Runtime behavior |
| --- | --- | --- |
| `safezones.yml` | Mapping of layout modes to named rectangles. A rectangle has `size.w`, `size.h`, `position.x`, and `position.y`. Current browser placement reads `match.stats` for match/freeplay and `menu.stats` for menu. | Served in `/layout.json` as `safezones`. Missing or invalid files fall back to built-in defaults and may add `warnings`. |
| `scoreboard-layouts.json` | JSON mapping for measured scoreboard element sizes and positions. | Served in `/layout.json` as `scoreboard_layouts`. The current browser overlay exposes it but does not render scoreboard elements yet. |
| `schemas/scoreboard-layouts.schema.json` | Draft reference schema for `scoreboard-layouts.json`. | Documentation/reference only until future validation tooling is added. |

Unknown local capture files can live under `.data`, but the app ignores them
unless code explicitly reads their filename.

## Generated Output Contract

| Path | Writer | Notes |
| --- | --- | --- |
| `rl_stats.sqlite3` | `StatsStore` through `listen.py` | Generated SQLite database for imported snapshots, live lifetime/session backing state, completed matches, player records, and shot speeds. Do not edit while the listener is running. |
| `latest_statsapi_frame.json` | `--latest-frame-json` without explicit path and without `--obs-dir` | Pretty JSON for the most recent decoded StatsAPI message. Overwritten in place. |
| `latest_statsapi_events.json` | `--latest-events-json` without explicit path and without `--obs-dir` | Pretty JSON object keyed by tracked event type. Known event keys initialize to `null`. |
| `latest_statsapi_events/*.json` | `--latest-events-dir` without explicit path and without `--obs-dir` | One pretty JSON file per tracked event type. Known event files initialize to `null`; unknown event filenames are sanitized. |

The SQLite schema is owned by `rl_statsapi_listener.overlay_state.StatsStore`.
Current tables are:

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

Treat SQLite tables as internal storage. Prefer the generated OBS text files,
`overlay_state.json`, `/state.json`, and `/layout.json` for overlay integration.

## Backup Workflow

Create a normal backup before large refactors, branch cleanup, or manual `.data`
edits:

```bash
.venv/bin/python tools/backup_data.py
```

The default output directory is `.local/backups/`, and archives are named:

```text
rl-statsapi-data-YYYYMMDD-HHMMSS.tar.gz
```

The archive stores files under a `.data/` prefix and includes
`.data/MANIFEST.sha256` with each archived file's SHA-256 hash, byte count, and
relative path. `.log` files are skipped by default.

Useful variants:

```bash
.venv/bin/python tools/backup_data.py --include-logs
.venv/bin/python tools/backup_data.py --output-dir ~/rl-statsapi-listener-backups
.venv/bin/python tools/backup_data.py --data-dir /path/to/data
```

Use an output directory outside the repo when the backup needs to survive
deleting or recreating the repository folder.

## Restore Workflow

Stop the listener and overlay host before restoring. If an existing `.data`
directory matters, create a fresh backup first.

Inspect the archive:

```bash
tar -tzf ~/rl-statsapi-listener-backups/rl-statsapi-data-YYYYMMDD-HHMMSS.tar.gz
```

Restore from the repository root:

```bash
tar -xzf ~/rl-statsapi-listener-backups/rl-statsapi-data-YYYYMMDD-HHMMSS.tar.gz -C .
```

That restores the archived `.data/...` paths, including `rl_stats.sqlite3` if it
was present. After restoring, start the listener normally.

If you want to rebuild SQLite from snapshots instead of restoring the archived
database, keep a backup, remove or move only `.data/rl_stats.sqlite3`, then run:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --reimport-snapshots
```

## Privacy

`.data` can contain display names, platform IDs, club roster details, match
records, and local career stats. Do not commit real `.data` files or generated
SQLite databases. Sanitized examples should live in a separate fixture directory
with fake player identifiers.
