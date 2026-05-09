# OBS Python Script Workflow

This workflow lets OBS connect directly to Rocket League StatsAPI and update
named OBS Text Sources without running the separate Python listener process.

## Use This When

- You want a simple scoreboard-style overlay inside OBS.
- You want OBS to receive values directly from StatsAPI.
- The fields you need are clock, blue score, orange score, event text, status,
  and team score colors.

Use the text-file or browser-overlay workflow instead when you need the richer
SQLite-backed match/session/lifetime stats.

## Files

```text
obs_rl_statsapi.py                    # Compatibility wrapper for existing OBS setups
integrations/obs/obs_rl_statsapi.py   # Canonical script implementation
```

Either file can be added to OBS, but edit the canonical script under
`integrations/obs/`.

## Setup

1. Enable Rocket League StatsAPI and restart Rocket League after changing its
   StatsAPI config.
2. In OBS, open `Tools > Scripts`.
3. Add `obs_rl_statsapi.py` from the repo root, or add
   `integrations/obs/obs_rl_statsapi.py` directly.
4. Create OBS Text Sources for the script outputs.
5. Set the source names in the script properties.

Default source names:

| Script setting | Default OBS source name |
| --- | --- |
| Clock Source Name | `RL Clock` |
| Blue Score Source Name | `RL Blue Score` |
| Orange Score Source Name | `RL Orange Score` |
| Event Source Name | `RL Event` |
| Status Source Name | `RL Status` |

The script connects to `127.0.0.1:49123` by default.

## Behavior

- `UpdateState` packets update clock, score, and team score colors.
- `ClockUpdatedSeconds` updates the clock when available.
- `GoalScored`, `MatchEnded`, and `RoundStarted` update event text.
- The OBS timer applies source updates at 10 Hz.
- The script reconnects after transient socket failures.

## Limitations

- This path does not use `.data/rl_stats.sqlite3`.
- It does not import `.data` snapshots.
- It does not expose Deja-Vu records, session/lifetime counters, freeplay speeds,
  Deaths, KD, or the browser-overlay state feed.
- Text background color support depends on the OBS text source type. Windows
  Text (GDI+) supports explicit background color; FreeType2 sources reliably
  support text color only.

## Troubleshooting

If the script says it cannot connect, confirm Rocket League StatsAPI is running
and that the host and port in the script settings still match the local
StatsAPI config.

If a source does not update, confirm the OBS source name exactly matches the
corresponding script setting. The script silently skips missing source names so
one missing source does not break the others.
