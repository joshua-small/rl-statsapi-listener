# Web Overlay Layout Data

The browser overlay uses two local JSON feeds:

- `/state.json`: live stats state from `OverlayStatsTracker`.
- `/layout.json`: local layout measurements loaded from `--data-dir`.

The layout feed lets the overlay use personal measurement files from `.data` without committing those files to git.

## Current Behavior

The overlay currently renders the stats surface in two placements:

```text
match/freeplay -> .data/safezones.yml -> match.stats
menu           -> .data/safezones.yml -> menu.stats
```

The default measured safezone rectangles are based on a `2560x1440` reference resolution:

```yaml
match:
  stats:
    size:
      w: 422
      h: 447
    position:
      x: 0
      y: 802
menu:
  stats:
    size:
      w: 684
      h: 102
    position:
      x: 1192
      y: 1238
```

The browser code scales the selected rectangle to the actual browser viewport. This keeps the stats content inside the measured safezone in OBS and in the Windows WebView host. The server and browser both infer the reference bounds from the largest safezone edges when possible, so entries such as `controller.y + controller.h = 1440` keep the vertical scale anchored correctly.

The in-match/freeplay view uses the taller stats panel with icons served from `/media/icons/stats/*.webp`. It shows live Match values, completed-session totals, per-completed-game averages, Deaths, KD, and your latest goal speed. The menu view uses a compact two-row strip to avoid party and chat UI.

The browser layout is covered by `tests/web_overlay.playwright.spec.js`, which checks `match.stats` and `menu.stats` placement, loaded icons, and screenshot output in Chromium.

## Layout Files

`.data/safezones.yml`

Stores measured safe rectangles for overlay surfaces. The implemented browser overlay reads `match.stats` when `context.mode` is `match` or `freeplay`, otherwise `menu.stats`. Other entries such as `match_conditions`, `series_wins`, `boost`, and `controller` are preserved as future layout data.

`.data/scoreboard-layouts.json`

Stores measured scoreboard element sizes and per-mode positions. The web server exposes this file as `scoreboard_layouts` in `/layout.json`, but the current browser overlay does not render scoreboard, clock, nameplate, boost, or series-win elements.

`.data/schemas/scoreboard-layouts.schema.json`

Draft schema/reference for the scoreboard layout capture data. Keep this aligned with the JSON file before building future theme renderers against it.

## Runtime Contract

`/layout.json` returns:

```json
{
  "reference_resolution": { "w": 2560, "h": 1440 },
  "safezones": {},
  "scoreboard_layouts": {},
  "warnings": []
}
```

Missing layout files are allowed. The server falls back to the current `match.stats` default and an empty scoreboard layout. Malformed files are reported in `warnings` so the overlay can still start. If safezone entries extend beyond the default reference bounds, `/layout.json` reports the larger inferred reference size.

## Future Theme Notes

The captured scoreboard layout data is intended for later RLCS-style broadcaster HUD themes. Useful next steps:

- Normalize the scoreboard layout JSON and schema so they agree on `layouts` versus `variants`.
- Add theme selection once there is more than one visual treatment.
- Apply the measured scoreboard-layout coordinates once the theme renderer is ready.
- Add per-resolution captures if the `2560x1440` reference does not scale cleanly enough for other displays.
