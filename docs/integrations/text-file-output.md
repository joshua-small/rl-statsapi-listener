# Text-File Output Workflow

This workflow runs the local listener and writes OBS-friendly `.txt` files that
OBS Text Sources can read from disk.

## Use This When

- You want SQLite-backed match/session/lifetime/freeplay/Deja-Vu values.
- You want to test new datapoints without changing the OBS Python script.
- Plain files are easier to wire into OBS than a browser source.
- You want latest StatsAPI JSON snapshots for payload inspection.

Use the OBS Python script workflow instead for the smallest direct OBS setup.
Use the browser overlay workflow when you want the built-in HTML/CSS stats panel.

## Start The Listener

```bash
.venv/bin/python listen.py --obs-dir ./obs-output
```

The listener will:

- Connect to `127.0.0.1:49123`.
- Import snapshots from `.data` on first database initialization.
- Create or update `.data/rl_stats.sqlite3`.
- Write OBS text files under `./obs-output`.
- Keep running until stopped with `Ctrl+C`.

Reimport updated manual snapshots:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --reimport-snapshots
```

Disable SQLite-backed overlay stats when you only need basic socket text files:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --no-overlay-stats
```

## OBS Setup

1. Create the output directory, for example `./obs-output`.
2. Start the listener with `--obs-dir`.
3. In OBS, add Text Sources.
4. For each Text Source, enable reading from a file.
5. Point each source at the matching generated `.txt` file.

## Generated Files

Basic socket files:

| File | Meaning |
| --- | --- |
| `clock.txt` | In-match clock. |
| `score_blue.txt` | Blue team score. |
| `score_orange.txt` | Orange team score. |
| `event_name.txt` | Latest StatsAPI event name. |
| `event_banner.txt` | Simple goal or match event text. |

SQLite-backed overlay files:

| File | Meaning |
| --- | --- |
| `session_wins.txt` | Wins since this listener run started. |
| `session_losses.txt` | Losses since this listener run started. |
| `session_streak.txt` | Current session streak, such as `W3` or `L2`. |
| `session_low_fives.txt` | Low fives this session. |
| `session_high_fives.txt` | High fives this session. |
| `session_demos.txt` | Demolitions this session. |
| `session_deaths.txt` | Times demolished this session. |
| `recent_mmr.txt` | Current playlist's stored MMR snapshot. |
| `lifetime_low_fives.txt` | Stored lifetime low fives. |
| `lifetime_high_fives.txt` | Stored lifetime high fives. |
| `lifetime_demos.txt` | Stored lifetime demolitions. |
| `lifetime_deaths.txt` | Stored lifetime deaths. |
| `last_goal_speed.txt` | Latest tracked goal speed. |
| `freeplay_last_shot.txt` | Latest tracked freeplay shot speed. |
| `freeplay_session_best.txt` | Best freeplay shot this listener run. |
| `freeplay_all_time_best.txt` | Best stored freeplay shot speed. |
| `freeplay_avg_last_10.txt` | Average of the last 10 stored shot speeds. |
| `club_name.txt` | Club tag/name. |
| `club_record.txt` | Compact club record summary. |
| `dejavu_players.txt` | Known players in the current match, when detected. |
| `overlay_state.json` | Structured state used by browser-style overlays. |

Replay speed output:

```bash
.venv/bin/python listen.py --obs-dir ./obs-output --replay-last-goal
.venv/bin/python listen.py --obs-dir ./obs-output --replay-goal-player-id 'Epic|account-id|0'
```

This writes `replay_last_goal.txt`. Start or restart the listener before
replaying the goal sequence so it can see the ball-speed frames before the score
changes.

## Payload Inspection Files

Use these flags when checking actual StatsAPI payload shape:

```bash
.venv/bin/python listen.py --pretty --latest-frame-json
.venv/bin/python listen.py --pretty --latest-events-json
.venv/bin/python listen.py --pretty --latest-events-dir
```

When no explicit path is passed, latest JSON outputs are written under
`--obs-dir` if present, otherwise under `--data-dir`.

## Troubleshooting

If files are not changing, confirm the listener is still connected, `--obs-dir`
points at the same directory OBS reads, and the event you expect is present in
the StatsAPI payload.

If session counters are not moving, run with `--pretty` and check whether
StatsAPI is sending the relevant player stat fields. Live Match values can move
before Session values; Session and lifetime counters only roll forward after a
start-confirmed, winner-bearing `MatchEnded`. Pregame cancellations such as
not-enough-players lobbies should leave these files unchanged.

If freeplay speed files do not update, run with `--latest-events-dir`, score a
freeplay goal, and inspect the files under `latest_statsapi_events/`.

The `.data` input and output contract is documented in `docs/data-contracts.md`.
