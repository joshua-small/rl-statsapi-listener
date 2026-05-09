# Media Asset Guide

This repository keeps source-controlled overlay imagery under `media/icons/`. Assets should be small, deterministic, and named for the semantic value the code displays, not for a temporary visual treatment.

## Naming Convention

Use `.webp` for overlay icons unless a future renderer requires a different format.

Directory rules:

| Directory | Convention | Meaning |
| --- | --- | --- |
| `media/icons/stats/` | `Title_Case_With_Underscores.webp` | Individual stat or accolade icons shown in the match/menu overlay. |
| `media/icons/playlists/` | Human-readable playlist names, such as `2v2.webp` or `Dropshot.webp` | Playlist/mode icons. |
| `media/icons/rank/` | Zero-padded order plus rank name, such as `13_Diamond1.webp` | Current rank icons in sorted progression order. |
| `media/icons/rank/old/` | Legacy rank filenames retained as-is | Previous rank icon set kept only for comparison or rollback. |

When adding new assets:

- Keep names stable once referenced by code or docs.
- Prefer semantic names over color/style descriptions.
- Avoid spaces in filenames.
- Add non-obvious icons to the manifest below.
- Update browser-rendering tests if the new asset must load in the overlay.

## Rank Icon Policy

`media/icons/rank/` is the active rank icon set. The numeric prefix preserves sort order from Unranked through Supersonic Legend.

`media/icons/rank/old/` is retained in the repo for now as an explicit rollback/comparison set. Do not reference it from runtime code. Revisit this directory after the active rank icons have been stable across a release or after an external asset archive exists.

## Lightweight Manifest

### Stat Icons

| File | Semantic meaning |
| --- | --- |
| `Aerial_Goal.webp` | Goal scored while airborne. |
| `Aerial_Hit.webp` | Ball hit while airborne. |
| `Assist.webp` | Assist stat. |
| `Backwards_Goal.webp` | Backwards goal accolade. |
| `Bicycle_Goal.webp` | Bicycle goal accolade. |
| `Bicycle_Hit.webp` | Bicycle hit accolade. |
| `Center_Ball.webp` | Center ball stat. |
| `Clear_Ball.webp` | Clear ball stat. |
| `Damage.webp` | Rumble-style damage stat. |
| `Demolition.webp` | Demolition inflicted by the player. |
| `Epic_Save.webp` | Epic save stat. |
| `Extermination.webp` | Extermination accolade. |
| `Exterminator.webp` | Exterminator accolade. |
| `First_Touch.webp` | First touch stat. |
| `Flip_Reset.webp` | Flip reset accolade/stat. |
| `Goal.webp` | Goal stat. |
| `Hat_Trick.webp` | Hat trick accolade. |
| `High_Five.webp` | High five stat. |
| `Juggle.webp` | Juggle accolade/stat. |
| `Long_Goal.webp` | Long goal accolade. |
| `Lose.webp` | Loss indicator. |
| `Low_Five.webp` | Low five stat. |
| `MVP.webp` | MVP accolade. |
| `Overtime_Goal.webp` | Overtime goal accolade. |
| `Playmaker.webp` | Playmaker accolade. |
| `Pool_Shot.webp` | Pool shot accolade. |
| `RIP.webp` | Deaths, meaning times demolished. |
| `Save.webp` | Save stat. |
| `Savior.webp` | Savior accolade. |
| `Shot_on_Goal.webp` | Shot stat. |
| `Swish_Goal.webp` | Hoops swish goal accolade. |
| `Turtle_Goal.webp` | Turtle goal accolade. |
| `Ultra_Damage.webp` | Rumble-style high damage stat. |
| `Win.webp` | Win indicator. |
| `streak.webp` | Session streak indicator. |

### Playlist Icons

| File | Semantic meaning |
| --- | --- |
| `1v1.webp` | Duel playlist. |
| `2v2.webp` | Doubles playlist. |
| `3v3.webp` | Standard playlist. |
| `4v4.webp` | Chaos playlist. |
| `Dropshot.webp` | Dropshot playlist. |
| `Hoops.webp` | Hoops playlist. |
| `Rumble.webp` | Rumble playlist. |
| `Snowday.webp` | Snow Day playlist. |

### Rank Icons

Rank filenames map directly to Rocket League rank progression:

```text
00_Unranked.webp
01_Bronze1.webp through 03_Bronze3.webp
04_Silver1.webp through 06_Silver3.webp
07_Gold1.webp through 09_Gold3.webp
10_Platinum1.webp through 12_Platinum3.webp
13_Diamond1.webp through 15_Diamond3.webp
16_Champion1.webp through 18_Champion3.webp
19_GrandChampion1.webp through 21_GrandChampion3.webp
22_SupersonicLegend.webp
```
