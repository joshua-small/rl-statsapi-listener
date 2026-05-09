# Browser Overlay Workflow

This workflow serves the built-in HTML/CSS/JavaScript overlay from the listener.
The same URL can be used by OBS Browser Source or by the Windows WebView host.

## Use This When

- You want the richer SQLite-backed stats without managing many OBS Text Sources.
- You want one visual overlay implementation that can run in OBS or in a
  transparent Windows host.
- You are iterating on layout with HTML, CSS, JavaScript, and measured safezones.

Use the text-file workflow when OBS should own the visual layout. Use the OBS
Python script workflow for the simplest direct scoreboard text setup.

## Start The Overlay

```bash
.venv/bin/python listen.py --web-overlay --obs-dir ./obs-output
```

Open:

```text
http://127.0.0.1:8765/
```

Useful feeds:

| URL | Meaning |
| --- | --- |
| `http://127.0.0.1:8765/` | Transparent overlay page. |
| `http://127.0.0.1:8765/state.json` | Structured live overlay state. |
| `http://127.0.0.1:8765/layout.json` | Safezone and layout measurements loaded from `--data-dir`. |

Use another port when needed:

```bash
.venv/bin/python listen.py --web-overlay --web-port 8766 --obs-dir ./obs-output
```

If Windows needs to reach a listener running inside WSL and `127.0.0.1` does not
bridge correctly, bind the listener to all interfaces:

```bash
.venv/bin/python listen.py --web-overlay --web-host 0.0.0.0 --obs-dir ./obs-output
```

Then use the WSL IP address from the Windows side.

## OBS Browser Source Setup

1. Start the listener with `--web-overlay`.
2. Add an OBS Browser Source.
3. Set the URL to `http://127.0.0.1:8765/`.
4. Set the source size to the game/output resolution.
5. Keep the source background transparent.

The page itself uses a transparent background. OBS or the window host is
responsible for preserving top-level transparency.

## Layout Behavior

The browser overlay currently chooses between two measured placements:

```text
match/freeplay -> .data/safezones.yml -> match.stats
menu           -> .data/safezones.yml -> menu.stats
```

The in-match/freeplay view shows live Match stats, completed-session totals,
per-completed-game averages, Deaths, KD, and latest goal speed. The menu view
uses a compact two-row stats strip.

See `docs/web-overlay-layout.md` for the safezone contract and current fallback
rectangles.

## Files

```text
rl_statsapi_listener/web_overlay_server.py
rl_statsapi_listener/web_overlay/index.html
rl_statsapi_listener/web_overlay/styles.css
rl_statsapi_listener/web_overlay/overlay.js
media/icons/stats/*.webp
```

## Verification

Run the Python tests after state-feed changes:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Run the browser-rendering tests after CSS, placement, icon, or feed-shape
changes:

```bash
npm run test:web
```

## Troubleshooting

If the overlay is blank, check the feed directly:

```bash
curl http://127.0.0.1:8765/state.json
curl http://127.0.0.1:8765/layout.json
```

If JSON loads but the OBS or WebView surface is stale, reload that host. In the
Windows WebView host, press `Ctrl+Shift+F11`.

If the overlay appears when it should be hidden, inspect `state.json` and check
`context.active` and `context.mode`. A stale browser source or old listener
process can keep old behavior visible after code changes.
