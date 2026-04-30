import tempfile
import textwrap
import unittest
from pathlib import Path

from rl_statsapi_listener.overlay_state import OverlayStatsTracker, StatsStore, load_yaml_like


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


class YamlLikeParserTests(unittest.TestCase):
    def test_parses_nested_lists_and_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "player_counter.yml"
            write(
                path,
                """
                players:
                  - uniqueId: player-1
                    metCount: 2
                    name: Teammate
                    playlists:
                      - playlistId: 11
                        records:
                          with:
                            wins: 1
                            losses: 0
                          against:
                            wins: 0
                            losses: 1
                """,
            )

            data = load_yaml_like(path)

        self.assertEqual(data["players"][0]["uniqueId"], "player-1")
        self.assertEqual(data["players"][0]["playlists"][0]["records"]["with"]["wins"], 1)
        self.assertEqual(data["players"][0]["playlists"][0]["records"]["against"]["losses"], 1)


class StatsStoreTests(unittest.TestCase):
    def test_imports_snapshots_and_tracks_match_updates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            obs_dir = root / "obs"
            db_path = root / "stats.sqlite3"

            write(
                data_dir / "player.yml",
                """
                datetime: 2026-04-29T13:43:14Z
                profile:
                  platform: steam
                  platformId: me-id
                  displayName: Me
                MMR:
                  - playlistId: 11
                    name: Ranked Doubles 2v2
                    value: 1155
                Career Record:
                  Total Matches Played: 20
                Stats:
                  Wins: 10
                  Low Fives: 2
                  High Fives: 1
                  Demolitions: 5
                """,
            )
            write(
                data_dir / "club.yml",
                """
                datetime: 2026-04-29T14:24:00Z
                Club Name: We Say Great Pass
                Club Tag: PASS
                Club Record:
                  Matches Played: 100
                  Win Ratio: 49.00
                Club Stats:
                  Wins: 49
                """,
            )
            write(
                data_dir / "club-roster.yml",
                """
                roster:
                  - platform: steam
                    platformId: me-id
                    displayName: Me
                """,
            )
            write(
                data_dir / "freeplay_goal.yml",
                """
                timestamp: 2026-04-29T21:04:12-07:00
                mode: freeplay
                goalSpeed: 118.4
                unit: kph
                result: goal
                """,
            )
            write(
                data_dir / "dejavu_player_counter.yml",
                """
                players:
                  - uniqueId: mate-id
                    metCount: 1
                    name: Old Mate
                    playlists:
                      - playlistId: 11
                        records:
                          with:
                            wins: 1
                            losses: 0
                """,
            )

            store = StatsStore(db_path, data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store, obs_dir=obs_dir)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "PlaylistId": 11,
                        "Game": {
                            "Teams": [
                                {"TeamNum": 0, "Score": 2},
                                {"TeamNum": 1, "Score": 1},
                            ],
                            "Players": [
                                {
                                    "UniqueId": "me-id",
                                    "Name": "Me",
                                    "TeamNum": 0,
                                    "Stats": {
                                        "gameLowFives": 1,
                                        "gameHighFives": 1,
                                        "gameDemolitions": 2,
                                    },
                                },
                                {"UniqueId": "mate-id", "Name": "Old Mate", "TeamNum": 0},
                                {"UniqueId": "opp-id", "Name": "Opponent", "TeamNum": 1},
                            ],
                        },
                    },
                }
            )
            tracker.handle_message({"Event": "MatchEnded", "Data": {"MatchGuid": "M1", "WinnerTeamNum": 0}})
            tracker.handle_message(
                {
                    "Event": "FreeplayGoalScored",
                    "Data": {"mode": "freeplay", "result": "goal", "goalSpeed": 132.4, "unit": "kph"},
                }
            )

            self.assertEqual(tracker.session_wins, 1)
            self.assertEqual(tracker.session_losses, 0)
            self.assertEqual(tracker.session_counts["low_fives"], 1)
            self.assertEqual(tracker.session_counts["high_fives"], 1)
            self.assertEqual(tracker.session_counts["demos"], 2)
            self.assertEqual(store.get_stat_value("career_stat", "Wins"), 11)
            self.assertEqual(store.get_stat_value("career_stat", "Career Record.Total Matches Played"), 21)
            self.assertEqual(store.get_stat_value("career_stat", "Low Fives"), 3)
            self.assertAlmostEqual(store.get_best_shot_speed(), 132.4)

            mate_record = store.get_dejavu_record("mate-id", 11, "with")
            opponent_record = store.get_dejavu_record("opp-id", 11, "against")
            self.assertEqual(mate_record["wins"], 2)
            self.assertEqual(opponent_record["wins"], 1)

            self.assertEqual((obs_dir / "session_wins.txt").read_text(encoding="utf-8"), "1")
            self.assertEqual((obs_dir / "session_streak.txt").read_text(encoding="utf-8"), "W1")
            self.assertEqual((obs_dir / "recent_mmr.txt").read_text(encoding="utf-8"), "Ranked Doubles 2v2: 1155")
            self.assertEqual((obs_dir / "freeplay_all_time_best.txt").read_text(encoding="utf-8"), "132.4 kph")

            store.close()


if __name__ == "__main__":
    unittest.main()
