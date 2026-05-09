import json
import threading
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
                            "TimeSeconds": 184,
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
                                        "Goals": 1,
                                        "gameLowFives": 1,
                                        "gameHighFives": 1,
                                        "gameDemolitions": 2,
                                    },
                                    "bDemolished": True,
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
            self.assertEqual(tracker.session_counts["goals"], 1)
            self.assertEqual(tracker.session_counts["low_fives"], 1)
            self.assertEqual(tracker.session_counts["high_fives"], 1)
            self.assertEqual(tracker.session_counts["demos"], 2)
            self.assertEqual(tracker.session_counts["deaths"], 1)
            self.assertEqual(store.get_stat_value("career_stat", "Wins"), 11)
            self.assertEqual(store.get_stat_value("career_stat", "Career Record.Total Matches Played"), 21)
            self.assertEqual(store.get_stat_value("career_stat", "Goals"), 1)
            self.assertEqual(store.get_stat_value("career_stat", "Low Fives"), 3)
            self.assertEqual(store.get_stat_value("career_stat", "Deaths"), 1)
            self.assertAlmostEqual(store.get_best_shot_speed(), 132.4)

            mate_record = store.get_dejavu_record("mate-id", 11, "with")
            opponent_record = store.get_dejavu_record("opp-id", 11, "against")
            self.assertEqual(mate_record["wins"], 2)
            self.assertEqual(opponent_record["wins"], 1)

            self.assertEqual((obs_dir / "session_wins.txt").read_text(encoding="utf-8"), "1")
            self.assertEqual((obs_dir / "session_streak.txt").read_text(encoding="utf-8"), "W1")
            self.assertEqual((obs_dir / "clock.txt").read_text(encoding="utf-8"), "3:04")
            self.assertEqual((obs_dir / "score_blue.txt").read_text(encoding="utf-8"), "2")
            self.assertEqual((obs_dir / "recent_mmr.txt").read_text(encoding="utf-8"), "Ranked Doubles 2v2: 1155")
            self.assertEqual((obs_dir / "freeplay_all_time_best.txt").read_text(encoding="utf-8"), "132.4 kph")

            web_state = json.loads((obs_dir / "overlay_state.json").read_text(encoding="utf-8"))
            self.assertEqual(web_state["context"]["mode"], "menu")
            self.assertFalse(web_state["context"]["active"])
            self.assertEqual(web_state["clock"], "3:04")
            self.assertEqual(web_state["scores"]["blue"], 2)
            self.assertEqual(web_state["session"]["wins"], 1)
            self.assertEqual(web_state["club"]["name"], "[PASS] We Say Great Pass")
            self.assertEqual(web_state["dejavu"][0]["display"], "Old Mate: with 2-0 (2)")

            store.close()

    def test_overlay_state_can_be_read_from_web_server_thread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            result = []
            errors = []

            def read_state() -> None:
                try:
                    result.append(tracker.get_overlay_state())
                except Exception as exc:
                    errors.append(exc)

            thread = threading.Thread(target=read_state)
            thread.start()
            thread.join()

            store.close()

        self.assertEqual(errors, [])
        self.assertEqual(result[0]["clock"], "0:00")
        self.assertEqual(result[0]["context"]["mode"], "menu")
        self.assertFalse(result[0]["context"]["active"])

    def test_infers_freeplay_from_update_state_without_match_guid_and_one_player(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                Stats:
                  Low Fives: 2
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [
                            {
                                "UniqueId": "me-id",
                                "Name": "Me",
                                "TeamNum": 0,
                                "Stats": {"gameLowFives": 1},
                            }
                        ],
                        "Game": {"TimeSeconds": 92},
                    },
                }
            )

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["context"]["mode"], "freeplay")
        self.assertTrue(state["context"]["active"])
        self.assertTrue(state["context"]["freeplay"])
        self.assertIsNone(state["match"]["guid"])
        self.assertEqual(state["clock"], "1:32")
        self.assertEqual(state["match"]["stats"]["low_fives"], 1)
        self.assertEqual(state["session"]["low_fives"], 0)

    def test_freeplay_goal_event_increments_live_goals_without_session_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 0}],
                            "Ball": {"Speed": 92.0},
                            "Elapsed": 10.0,
                            "Frame": 600,
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "FreeplayGoalScored",
                    "Data": {"mode": "freeplay", "result": "goal", "goalSpeed": 128.4, "unit": "kph"},
                }
            )

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["context"]["mode"], "freeplay")
        self.assertEqual(state["match"]["stats"]["goals"], 1)
        self.assertEqual(state["match"]["last_goal_speed"], "128.4 kph")
        self.assertEqual(state["session"]["goals"], 0)

    def test_freeplay_update_state_score_increase_counts_goal_without_goal_event(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0, "Stats": {"Goals": 0}}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 0}],
                            "Ball": {"Speed": 88.0},
                            "Elapsed": 20.0,
                            "Frame": 1200,
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0, "Stats": {"Goals": 0}}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 0}],
                            "Ball": {"Speed": 132.4},
                            "Elapsed": 20.2,
                            "Frame": 1212,
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0, "Stats": {"Goals": 0}}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 1}],
                            "Ball": {"Speed": 0.0},
                            "Elapsed": 20.4,
                            "Frame": 1224,
                        },
                    },
                }
            )

            state = tracker.get_overlay_state()
            last_shot = store.get_last_shot_speed()
            store.close()

        self.assertEqual(state["context"]["mode"], "freeplay")
        self.assertEqual(state["match"]["stats"]["goals"], 1)
        self.assertEqual(state["match"]["last_goal_speed"], "132.4 kph")
        self.assertEqual(state["session"]["goals"], 0)
        self.assertAlmostEqual(last_shot, 132.4)

    def test_freeplay_update_state_score_increase_without_speed_keeps_last_speed_blank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 0}],
                            "Ball": {"Speed": 0.0},
                            "Elapsed": 40.0,
                            "Frame": 2400,
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 1}],
                            "Ball": {"Speed": 0.0},
                            "Elapsed": 40.2,
                            "Frame": 2412,
                        },
                    },
                }
            )

            state = tracker.get_overlay_state()
            last_shot = store.get_last_shot_speed()
            store.close()

        self.assertEqual(state["match"]["stats"]["goals"], 1)
        self.assertEqual(state["match"]["last_goal_speed"], "-- kph")
        self.assertIsNone(last_shot)

    def test_freeplay_score_increase_after_goal_event_does_not_double_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 0}],
                            "Ball": {"Speed": 100.0},
                            "Elapsed": 30.0,
                            "Frame": 1800,
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "FreeplayGoalScored",
                    "Data": {
                        "mode": "freeplay",
                        "result": "goal",
                        "goalSpeed": 111.0,
                        "unit": "kph",
                        "Elapsed": 30.1,
                        "Frame": 1806,
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0, "Stats": {"Goals": 0}}],
                        "Game": {
                            "Teams": [{"TeamNum": 0, "Score": 1}],
                            "Ball": {"Speed": 120.0},
                            "Elapsed": 30.2,
                            "Frame": 1812,
                        },
                    },
                }
            )

            state = tracker.get_overlay_state()
            last_shot = store.get_last_shot_speed()
            store.close()

        self.assertEqual(state["match"]["stats"]["goals"], 1)
        self.assertEqual(state["match"]["last_goal_speed"], "111 kph")
        self.assertAlmostEqual(last_shot, 111.0)

    def test_private_match_destroyed_before_winner_keeps_live_stats_out_of_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: other-profile
                  displayName: Other Profile
                Stats:
                  Demolitions: 10
                  Deaths: 5
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "PRIVATE1",
                        "Game": {
                            "TimeSeconds": 120,
                            "Teams": [{"TeamNum": 0, "Score": 3}, {"TeamNum": 1, "Score": 1}],
                            "Players": [
                                {
                                    "UniqueId": "Steam|76561198080314981|0",
                                    "Name": "Noooo! Great Pass!",
                                    "TeamNum": 0,
                                    "Demos": 1,
                                    "bDemolished": False,
                                },
                                {
                                    "UniqueId": "opp-id",
                                    "Name": "Opponent",
                                    "TeamNum": 1,
                                    "Boost": 0,
                                    "bDemolished": True,
                                },
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "PRIVATE1",
                        "Game": {
                            "Players": [
                                {
                                    "UniqueId": "Steam|76561198080314981|0",
                                    "Name": "Noooo! Great Pass!",
                                    "TeamNum": 0,
                                    "Demos": 1,
                                    "bDemolished": True,
                                }
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "PRIVATE1",
                        "Game": {
                            "Players": [
                                {
                                    "UniqueId": "Steam|76561198080314981|0",
                                    "Name": "Noooo! Great Pass!",
                                    "TeamNum": 0,
                                    "Demos": 1,
                                    "bDemolished": True,
                                }
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "PRIVATE1",
                        "Game": {
                            "Players": [
                                {
                                    "UniqueId": "Steam|76561198080314981|0",
                                    "Name": "Noooo! Great Pass!",
                                    "TeamNum": 0,
                                    "Demos": 1,
                                    "bDemolished": False,
                                }
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "PRIVATE1",
                        "Game": {
                            "Players": [
                                {
                                    "UniqueId": "Steam|76561198080314981|0",
                                    "Name": "Noooo! Great Pass!",
                                    "TeamNum": 0,
                                    "Demos": 1,
                                    "bDemolished": True,
                                }
                            ],
                        },
                    },
                }
            )
            live_state = tracker.get_overlay_state()

            tracker.handle_message({"Event": "MatchEnded", "Data": {"MatchGuid": "PRIVATE1", "WinnerTeamNum": -1}})
            no_winner_state = tracker.get_overlay_state()
            tracker.handle_message({"Event": "MatchDestroyed", "Data": {"MatchGuid": "PRIVATE1"}})
            state = tracker.get_overlay_state()

            self.assertEqual(live_state["match"]["stats"]["demos"], 1)
            self.assertEqual(live_state["match"]["stats"]["deaths"], 2)
            self.assertEqual(live_state["session"]["demos"], 0)
            self.assertEqual(live_state["session"]["deaths"], 0)
            self.assertEqual(no_winner_state["session"]["wins"], 0)
            self.assertEqual(no_winner_state["session"]["losses"], 0)
            self.assertEqual(no_winner_state["session"]["demos"], 0)
            self.assertEqual(no_winner_state["session"]["deaths"], 0)
            self.assertEqual(state["session"]["wins"], 0)
            self.assertEqual(state["session"]["losses"], 0)
            self.assertEqual(state["session"]["demos"], 0)
            self.assertEqual(state["session"]["deaths"], 0)
            self.assertEqual(store.get_stat_value("career_stat", "Demolitions"), 10)
            self.assertEqual(store.get_stat_value("career_stat", "Deaths"), 5)
            store.close()

    def test_match_ended_without_start_evidence_does_not_count_loss(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                Career Record:
                  Total Matches Played: 20
                Stats:
                  Losses: 4
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {"Event": "MatchInitialized", "Data": {"MatchGuid": "CANCELLED1"}}
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "CANCELLED1",
                        "Game": {
                            "TimeSeconds": 92,
                            "Teams": [
                                {"TeamNum": 0, "Score": 0},
                                {"TeamNum": 1, "Score": 0},
                            ],
                            "Players": [
                                {
                                    "UniqueId": "me-id",
                                    "Name": "Me",
                                    "TeamNum": 0,
                                    "Stats": {
                                        "Goals": 0,
                                        "Assists": 0,
                                        "Saves": 0,
                                        "Shots": 0,
                                    },
                                }
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "MatchEnded",
                    "Data": {"MatchGuid": "CANCELLED1", "WinnerTeamNum": 1},
                }
            )

            state = tracker.get_overlay_state()
            self.assertEqual(state["session"]["wins"], 0)
            self.assertEqual(state["session"]["losses"], 0)
            self.assertEqual(state["session"]["streak"], "0")
            self.assertEqual(store.get_stat_value("career_stat", "Losses"), 4)
            self.assertEqual(
                store.get_stat_value("career_stat", "Career Record.Total Matches Played"),
                20,
            )
            self.assertFalse(store.match_exists("CANCELLED1"))
            self.assertEqual(state["context"]["mode"], "menu")
            self.assertFalse(state["context"]["active"])
            store.close()

    def test_round_started_allows_zero_score_match_end_to_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {"Event": "MatchInitialized", "Data": {"MatchGuid": "STARTED1"}}
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "STARTED1",
                        "Game": {
                            "Teams": [
                                {"TeamNum": 0, "Score": 0},
                                {"TeamNum": 1, "Score": 0},
                            ],
                            "Players": [
                                {"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}
                            ],
                        },
                    },
                }
            )
            tracker.handle_message(
                {"Event": "RoundStarted", "Data": {"MatchGuid": "STARTED1"}}
            )
            tracker.handle_message(
                {
                    "Event": "MatchEnded",
                    "Data": {"MatchGuid": "STARTED1", "WinnerTeamNum": 0},
                }
            )

            state = tracker.get_overlay_state()
            self.assertEqual(state["session"]["wins"], 1)
            self.assertEqual(state["session"]["losses"], 0)
            self.assertTrue(store.match_exists("STARTED1"))
            store.close()

    def test_last_goal_speed_tracks_only_known_self_scorers_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "GoalScored",
                    "Data": {
                        "Scorer": {"PrimaryId": "Epic|someone-else|0", "Name": "Other"},
                        "goalSpeed": 91.2,
                        "unit": "kph",
                    },
                }
            )
            self.assertEqual(tracker.get_overlay_state()["match"]["last_goal_speed"], "-- kph")

            tracker.handle_message(
                {
                    "Event": "GoalScored",
                    "Data": {
                        "Scorer": {
                            "PrimaryId": "Epic|27492b8e1d074bd69f93fefc7c284205|0",
                            "Name": "NoNoNo GreatPass",
                        },
                        "goalSpeed": 123.4,
                        "unit": "kph",
                    },
                }
            )
            self.assertEqual(tracker.get_overlay_state()["match"]["last_goal_speed"], "123.4 kph")

            tracker.handle_message({"Event": "MatchDestroyed", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M2"}})
            self.assertEqual(tracker.get_overlay_state()["match"]["last_goal_speed"], "123.4 kph")

            tracker.handle_message(
                {
                    "Event": "GoalScored",
                    "Data": {
                        "Scorer": {"PrimaryId": "Steam|someone-else|0", "Name": "Opponent"},
                        "goalSpeed": 140.0,
                        "unit": "kph",
                    },
                }
            )
            self.assertEqual(tracker.get_overlay_state()["match"]["last_goal_speed"], "123.4 kph")
            store.close()

    def test_infers_menu_from_update_state_without_match_guid_and_no_players(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        "Game": {"TimeSeconds": 92},
                    },
                }
            )
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {"MatchGuid": "", "Players": [], "Game": {"TimeSeconds": 0}},
                }
            )

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["context"]["mode"], "menu")
        self.assertFalse(state["context"]["active"])
        self.assertIsNone(state["match"]["guid"])

    def test_match_ended_counts_match_then_deactivates_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / ".data"
            write(
                data_dir / "player.yml",
                """
                profile:
                  platformId: me-id
                  displayName: Me
                Stats:
                  Wins: 10
                """,
            )
            store = StatsStore(root / "stats.sqlite3", data_dir)
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Game": {
                            "TimeSeconds": 184,
                            "Teams": [{"TeamNum": 0, "Score": 2}, {"TeamNum": 1, "Score": 1}],
                            "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                        },
                    },
                }
            )
            tracker.handle_message({"Event": "MatchEnded", "Data": {"MatchGuid": "M1", "WinnerTeamNum": 0}})

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["session"]["wins"], 1)
        self.assertEqual(state["context"]["mode"], "menu")
        self.assertFalse(state["context"]["active"])
        self.assertFalse(state["match"]["active"])
        self.assertEqual(state["match"]["guid"], "M1")

    def test_podium_start_deactivates_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "PodiumStart", "Data": {"MatchGuid": "M1"}})

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["context"]["mode"], "menu")
        self.assertFalse(state["context"]["active"])

    def test_match_destroyed_deactivates_and_clears_match_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "MatchDestroyed", "Data": {"MatchGuid": "M1"}})

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["event"]["name"], "MatchDestroyed")
        self.assertEqual(state["context"]["mode"], "menu")
        self.assertFalse(state["context"]["active"])
        self.assertIsNone(state["match"]["guid"])

    def test_stale_update_state_after_match_destroyed_does_not_reactivate_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "MatchDestroyed", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Players": [{"UniqueId": "me-id", "Name": "Me", "TeamNum": 0}],
                    },
                }
            )

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["event"]["name"], "UpdateState")
        self.assertEqual(state["context"]["mode"], "menu")
        self.assertFalse(state["context"]["active"])
        self.assertIsNone(state["match"]["guid"])

    def test_new_match_initialized_can_reactivate_after_destroyed_guid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = StatsStore(root / "stats.sqlite3", root / ".data")
            store.initialize()
            tracker = OverlayStatsTracker(store)

            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "MatchDestroyed", "Data": {"MatchGuid": "M1"}})
            tracker.handle_message({"Event": "MatchInitialized", "Data": {"MatchGuid": "M2"}})

            state = tracker.get_overlay_state()
            store.close()

        self.assertEqual(state["context"]["mode"], "match")
        self.assertTrue(state["context"]["active"])
        self.assertEqual(state["match"]["guid"], "M2")


if __name__ == "__main__":
    unittest.main()
