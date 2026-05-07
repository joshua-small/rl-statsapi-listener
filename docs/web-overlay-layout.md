# Web Overlay Layout Data

The browser overlay uses two local JSON feeds:

- `/state.json`: live stats state from `OverlayStatsTracker`.
- `/layout.json`: local layout measurements loaded from `--data-dir`.

The layout feed lets the overlay use personal measurement files from `.data` without committing those files to git.

## Current Behavior

The overlay currently renders only the stats HUD. It positions and clips that HUD to:

```text
.data/safezones.yml -> match.stats
```

The current measured rectangle is based on a `2560x1140` reference resolution:

```yaml
match:
  stats:
    size:
      w: 422
      h: 447
    position:
      x: 0
      y: 802
```

The browser code scales that rectangle to the actual browser viewport. This keeps the stats content inside the measured safezone in OBS and in the Windows WebView host.

## Layout Files

`.data/safezones.yml`

Stores measured safe rectangles for overlay surfaces. The implemented browser overlay only reads `match.stats` today. Other entries such as `clock`, `match_conditions`, `series_wins`, `team1_score`, `team2_score`, `boost`, and `controller` are preserved as future layout data.

`.data/scoreboard-layouts.json`

Stores measured scoreboard element sizes and per-mode positions. The web server exposes this file as `scoreboard_layouts` in `/layout.json`, but the current HTML/CSS/JS does not render scoreboard, clock, team score, boost, or series-win elements yet.

`.data/schemas/scoreboard-layouts.schema.json`

Draft schema/reference for the scoreboard layout capture data. Keep this aligned with the JSON file before building future theme renderers against it.

## Runtime Contract

`/layout.json` returns:

```json
{
  "reference_resolution": { "w": 2560, "h": 1140 },
  "safezones": {},
  "scoreboard_layouts": {},
  "warnings": []
}
```

Missing layout files are allowed. The server falls back to the current `match.stats` default and an empty scoreboard layout. Malformed files are reported in `warnings` so the overlay can still start.

## Future Theme Notes

The captured scoreboard layout data is intended for later RLCS-style broadcaster HUD themes. Useful next steps:

- Normalize the scoreboard layout JSON and schema so they agree on `layouts` versus `variants`.
- Add theme selection once there is more than one visual treatment.
- Render scoreboard/clock/team/boost elements only when their safezone and game context are known.
- Add per-resolution captures if the `2560x1140` reference does not scale cleanly enough for other displays.
