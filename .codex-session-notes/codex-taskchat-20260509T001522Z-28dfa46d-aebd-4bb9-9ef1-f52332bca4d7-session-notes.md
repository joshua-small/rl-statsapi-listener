# Codex Session Notes

## Instance

- Instance ID: `codex-taskchat-20260509T001522Z-28dfa46d-aebd-4bb9-9ef1-f52332bca4d7`
- Created: 2026-05-08 17:15:22 PDT -0700
- Repository: `/home/small/rl-statsapi-listener`
- Previous archived task/chat notes: `.codex/codex-taskchat-20260509T000406Z-01b06679-3f28-4a89-8634-74b1431ffc29-session-notes.md`
- Context limitation: This assistant instance worked from this chat, the local repository, and command output. It did not inspect other task/chat transcripts.

## Task Chat Summary

### Freeplay Overlay Placement

- Changed the browser overlay so `context.mode === "freeplay"` uses the same visual layout and safezone as matches.
- `match` and `freeplay` now render in `match.stats`.
- `menu` continues to render in `menu.stats`.
- Added Playwright coverage proving Freeplay uses `match.stats`.

### Match, Session, And Career Stat Semantics

- Stopped live match stat deltas from being immediately added to session and career counters.
- Session and lifetime stats now increment only when `MatchEnded` has a real winner team, `WinnerTeamNum` of `0` or `1`.
- Private matches ended early, including `WinnerTeamNum: -1`, keep live Match stats visible but do not alter Session or career totals.
- Removed fallback winner inference from score because it could incorrectly count unfinished private matches.
- Added tests covering cancelled private matches and winner-bearing completed matches.

### Deaths And KD

- Added Deaths as a tracked stat.
- Deaths are tracked from the local player's `bDemolished` false-to-true transitions because StatsAPI does not provide a direct live deaths counter.
- Added `RIP.webp` to the in-match stats grid.
- Added KD as a text glyph row.
- KD is calculated from Demolitions divided by Deaths.
- Added `session_deaths.txt`, `lifetime_deaths.txt`, and Deaths in overlay state output.

### Last Goal Speed

- Added persistent `match.last_goal_speed` to the overlay state.
- Added `last_goal_speed.txt` for OBS text output.
- The browser renders the value as a fourth Goals-row value, formatted as number plus smaller `KPH`.
- The speed persists until the next tracked self goal.
- Match/replay goal speeds are only accepted for known self identities:
  - `Steam|76561198080314981|0`
  - `Epic|27492b8e1d074bd69f93fefc7c284205|0`
  - `Epic|399c852cc7ea4522b9e53f472e9f6f2a|0`
  - Matching display-name tokens for the known names provided in the chat.
- Freeplay goals with no scorer are treated as self goals only while the current mode is Freeplay.
- Added tests for self-only goal speed tracking and persistence across match resets.

### Freeplay Goal Fallback

- Added a Freeplay fallback for cases such as "Disable Goal Reset" where normal goal events may not arrive.
- While in Freeplay, the tracker keeps a short rolling window of positive `UpdateState.Game.Ball.Speed` samples.
- If `UpdateState.Game.Teams[].Score` increases in Freeplay, the tracker counts a live Match goal and uses the best recent ball speed as the goal speed.
- Added dedupe handling so a normal Freeplay goal event followed by a score bump does not double-count.
- If no positive ball speed is available, the inferred goal still counts but last-goal speed is left unchanged rather than recording `0 kph`.
- Added tests for:
  - Freeplay goal event increments live Match goals without Session stats.
  - Freeplay score increase increments live Match goals without a goal event.
  - No-speed score increase keeps last-goal speed blank.
  - Goal event plus score increase does not double-count.

### Nameplates And Scoreboard Work

- The player nameplate/boost idea was intentionally tabled because `UpdateState` does not report boost for opposing players from the local StatsAPI instance.
- Removed visible scoreboard/nameplate rendering from the browser overlay work in this chat.
- Tests assert no `#scoreboardSafezone` or `[data-player-id]` elements are rendered.
- `.data/scoreboard-layouts.json` continues to be exposed for future work, but the current browser overlay does not render scoreboard, clock, nameplate, boost, or series-win elements.

### In-Match Stats Grid UI

- Removed the Shots row from the visible in-match grid.
- Added Deaths and KD rows.
- Added last goal speed into the Goals row as a fourth value with no column header.
- Unified stat icon/glyph footprints at `44px`.
- Made the summary strip values use the same responsive number sizing as stats-grid values.
- Reduced the `KPH` unit size so it reads as a unit label rather than a second large value.
- Added Playwright assertions for icon sizes, summary/grid font-size consistency, and smaller speed-unit sizing.

### Menu Stats Layout

- Moved the menu stats overlay away from party/chat UI.
- Updated tracked fallback `menu.stats` to `{w:684,h:102,x:1192,y:1238}` on a `2560x1440` reference canvas.
- Updated local ignored `.data/safezones.yml` with the same menu safezone:
  - `x: 1192`
  - `y: 1238`
  - `w: 684`
  - `h: 102`
- The bottom edge remains anchored at `1340`.
- The right edge is now `1876`.
- Reworked the menu strip from one cramped row to a compact 4-column, 2-row grid.
- Reduced menu-only value sizing to prevent clipping in the smaller box.
- Added Playwright checks that menu stat items and values fit inside their cells.

### Documentation Updates

- Updated `README.md` with:
  - Freeplay using `match.stats`.
  - The compact two-row menu strip and current fallback safezone rectangles.
  - Deaths, KD, and latest goal speed behavior.
  - Session/lifetime stats only updating after winner-bearing matches.
  - Freeplay score-increase fallback and no-speed behavior.
  - New OBS text outputs for deaths and last goal speed.
- Updated `docs/web-overlay-layout.md` with:
  - `match/freeplay -> match.stats`.
  - `menu -> menu.stats`.
  - Current menu rectangle `{w:684,h:102,x:1192,y:1238}`.
  - Current non-rendering status for scoreboard, clock, nameplate, boost, and series-win elements.

## Verification Run

- `python -m unittest discover tests` passed with 34 tests.
- `npm run test:web` passed with 3 Playwright tests.
- `git diff --check` passed.

## Important Local State

- At note creation, `git status --short` printed no tracked changes.
- `.codex/` is ignored by git; this notes file is local archive context unless force-added.
- `.data/` is ignored by git; the local `.data/safezones.yml` was updated during this chat but is not tracked by default.
- The requested archived predecessor notes file exists at `.codex/codex-taskchat-20260509T000406Z-01b06679-3f28-4a89-8634-74b1431ffc29-session-notes.md`.

## Suggested Commit Message From This Task Chat

```text
Refine live stats tracking and compact overlay layout

- use match.stats for Freeplay and add Deaths, KD, and last goal speed
- only roll match stats into session totals after winner-bearing matches
- track deaths from demolition state and infer Freeplay goals from score bumps
- compact the menu stats strip into a two-row layout away from party/chat UI
- update overlay docs and regression coverage
```
