# Test Suite Guide

This suite is split by behavioral surface rather than by implementation file. Keep new tests close to the user-facing contract they protect.

## Run Paths

Fast Python pass:

```bash
npm run test:python
```

Equivalent direct command:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Full local pass for changes that touch overlay rendering, safezone layout, browser assets, or web feed behavior:

```bash
npm run check
```

Fast hygiene pass for docs-only or Python-only changes:

```bash
npm run check:quick
```

`check:quick` runs text-format checks, Python compile checks, documentation
checks, Python tests, and JavaScript syntax checks. `check` adds the Playwright
browser-rendering tests.

Use headed browser tests only while debugging layout interactively:

```bash
npm run test:web:headed
```

## Test Groups

| Group | Current files | Coverage |
| --- | --- | --- |
| State logic | `test_overlay_state.py` | YAML-like snapshot parsing, SQLite imports, match/session/lifetime counters, Freeplay state, match lifecycle handling, overlay state generation. |
| CLI and OBS file behavior | `test_cli_obs.py` | OBS text-file output helpers, replay last-goal speed handling, latest StatsAPI frame/event JSON writers, event filename safety. |
| Entry-point contracts | `test_entry_points.py` | Root compatibility wrappers and the installed console-script target stay pointed at the canonical implementation modules. |
| Web overlay feed contracts | `test_web_overlay_server.py` | Safezone and scoreboard layout loading for `/layout.json`, including defaults when local data files are absent. |
| Browser rendering | `web_overlay.playwright.spec.js` | Real browser checks for match, Freeplay, and menu layouts, icon loading, safezone placement, text fit, and screenshot artifacts. |
| Integration contracts | Spread across Python and Playwright tests | Contracts between listener state, generated JSON/text files, and the browser overlay. Add dedicated tests here when a feature crosses module boundaries. |

## Fixture Policy

Prefer temporary directories and inline minimal payloads for narrow state tests. They make each test self-contained and keep personal `.data` files out of source control.

Centralize a fixture only when at least two test files need the same shape or when copying the payload would obscure the assertion. Current candidates for future centralization:

- A minimal `.data` snapshot set with `player.yml`, `club.yml`, `club-roster.yml`, `freeplay_goal.yml`, and `dejavu_player_counter.yml`.
- Canonical `UpdateState` payloads for match, Freeplay, replay, and menu/inactive states.
- The default safezone layout used by both `test_web_overlay_server.py` and `web_overlay.playwright.spec.js`.

Keep centralized fixtures sanitized and deterministic. Do not commit real `.data` content or generated SQLite databases.
