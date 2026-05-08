import tempfile
import unittest
from pathlib import Path

from rl_statsapi_listener.cli import (
    initialize_latest_event_files,
    initialize_latest_events_by_type,
    resolve_latest_events_dir_path,
    resolve_latest_events_json_path,
    resolve_latest_frame_json_path,
    safe_event_filename,
    initialize_replay_last_goal_file,
    write_latest_event_file,
    update_latest_events_by_type,
    update_obs_files,
    write_latest_events_json,
    write_latest_frame_json,
)


TARGET_ID = "Epic|399c852cc7ea4522b9e53f472e9f6f2a|0"


class ReplayLastGoalObsTests(unittest.TestCase):
    def test_replay_last_goal_uses_target_ball_hit_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_dir = Path(tmp)
            cache = {}
            state = {}

            initialize_replay_last_goal_file(obs_dir, cache)
            update_obs_files(
                {
                    "Event": "BallHit",
                    "Data": {
                        "Player": {"PrimaryId": TARGET_ID, "Name": "Small"},
                        "Ball": {"PostHitSpeed": 121.24},
                    },
                },
                obs_dir,
                cache,
                replay_goal_player_id=TARGET_ID,
                replay_goal_state=state,
            )
            self.assertEqual((obs_dir / "replay_last_goal.txt").read_text(encoding="utf-8"), "-- kph")

            update_obs_files(
                {"Event": "GoalScored", "Data": {"Scorer": {"PrimaryId": TARGET_ID, "Name": "Small"}}},
                obs_dir,
                cache,
                replay_goal_player_id=TARGET_ID,
                replay_goal_state=state,
            )

            self.assertEqual((obs_dir / "replay_last_goal.txt").read_text(encoding="utf-8"), "121.2 kph")

    def test_replay_last_goal_ignores_other_scorers(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_dir = Path(tmp)
            cache = {}
            state = {}

            initialize_replay_last_goal_file(obs_dir, cache)
            update_obs_files(
                {
                    "Event": "GoalScored",
                    "Data": {
                        "Scorer": {"PrimaryId": "Epic|someone-else|0", "Name": "Other"},
                        "Ball": {"PostHitSpeed": 99.0},
                    },
                },
                obs_dir,
                cache,
                replay_goal_player_id=TARGET_ID,
                replay_goal_state=state,
            )

            self.assertEqual((obs_dir / "replay_last_goal.txt").read_text(encoding="utf-8"), "-- kph")

    def test_replay_last_goal_reads_direct_mph_speed(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_dir = Path(tmp)
            cache = {}
            state = {}

            initialize_replay_last_goal_file(obs_dir, cache)
            update_obs_files(
                {
                    "Event": "GoalScored",
                    "Data": {
                        "Scorer": {"PrimaryId": TARGET_ID, "Name": "Small"},
                        "Ball": {"PostHitSpeed": 70, "Unit": "mph"},
                    },
                },
                obs_dir,
                cache,
                replay_goal_player_id=TARGET_ID,
                replay_goal_state=state,
            )

            self.assertEqual((obs_dir / "replay_last_goal.txt").read_text(encoding="utf-8"), "112.7 kph")

    def test_replay_last_goal_uses_update_state_score_increase(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_dir = Path(tmp)
            cache = {}
            state = {}

            initialize_replay_last_goal_file(obs_dir, cache)
            update_obs_files(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Game": {
                            "Frame": 100,
                            "Elapsed": 10.0,
                            "Ball": {"Speed": 97.4},
                            "Teams": [{"TeamNum": 0, "Score": 1}, {"TeamNum": 1, "Score": 1}],
                            "bReplay": True,
                        },
                    },
                },
                obs_dir,
                cache,
                replay_goal_state=state,
            )
            update_obs_files(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Game": {
                            "Frame": 130,
                            "Elapsed": 10.5,
                            "Ball": {"Speed": 126.8},
                            "Teams": [{"TeamNum": 0, "Score": 1}, {"TeamNum": 1, "Score": 1}],
                            "bReplay": True,
                        },
                    },
                },
                obs_dir,
                cache,
                replay_goal_state=state,
            )
            update_obs_files(
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Game": {
                            "Frame": 150,
                            "Elapsed": 11.0,
                            "Ball": {"Speed": 0.0},
                            "Teams": [{"TeamNum": 0, "Score": 1}, {"TeamNum": 1, "Score": 2}],
                            "bReplay": True,
                        },
                    },
                },
                obs_dir,
                cache,
                replay_goal_state=state,
            )

            self.assertEqual((obs_dir / "replay_last_goal.txt").read_text(encoding="utf-8"), "126.8 kph")


class LatestFrameJsonTests(unittest.TestCase):
    def test_writes_pretty_latest_frame_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest_statsapi_frame.json"

            write_latest_frame_json(
                path,
                {
                    "Event": "UpdateState",
                    "Data": {
                        "MatchGuid": "M1",
                        "Game": {"Frame": 42, "TimeSeconds": 184},
                    },
                },
            )

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n'
                '  "Event": "UpdateState",\n'
                '  "Data": {\n'
                '    "MatchGuid": "M1",\n'
                '    "Game": {\n'
                '      "Frame": 42,\n'
                '      "TimeSeconds": 184\n'
                "    }\n"
                "  }\n"
                "}\n",
            )

    def test_default_path_prefers_obs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_frame_json_path("", root / "obs-output", root / ".data"),
                root / "obs-output" / "latest_statsapi_frame.json",
            )

    def test_default_path_falls_back_to_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_frame_json_path("", None, root / ".data"),
                root / ".data" / "latest_statsapi_frame.json",
            )


class LatestEventsJsonTests(unittest.TestCase):
    def test_initializes_known_event_placeholders(self):
        events_by_type = initialize_latest_events_by_type()

        self.assertIn("UpdateState", events_by_type)
        self.assertIn("BallHit", events_by_type)
        self.assertIn("StatfeedEvent", events_by_type)
        self.assertIsNone(events_by_type["GoalScored"])

    def test_writes_latest_message_by_event_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest_statsapi_events.json"
            events_by_type = initialize_latest_events_by_type()

            update_latest_events_by_type(
                events_by_type,
                {"Event": "BallHit", "Data": {"Ball": {"PostHitSpeed": 121.24}}},
            )
            update_latest_events_by_type(
                events_by_type,
                {"Event": "GoalScored", "Data": {"Scorer": {"Name": "Small"}}},
            )
            update_latest_events_by_type(
                events_by_type,
                {"Event": "BallHit", "Data": {"Ball": {"PostHitSpeed": 132.4}}},
            )
            write_latest_events_json(path, events_by_type)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n'
                '  "UpdateState": null,\n'
                '  "BallHit": {\n'
                '    "Event": "BallHit",\n'
                '    "Data": {\n'
                '      "Ball": {\n'
                '        "PostHitSpeed": 132.4\n'
                "      }\n"
                "    }\n"
                "  },\n"
                '  "ClockUpdatedSeconds": null,\n'
                '  "CountdownBegin": null,\n'
                '  "CrossbarHit": null,\n'
                '  "GoalReplayEnd": null,\n'
                '  "GoalReplayStart": null,\n'
                '  "GoalReplayWillEnd": null,\n'
                '  "GoalScored": {\n'
                '    "Event": "GoalScored",\n'
                '    "Data": {\n'
                '      "Scorer": {\n'
                '        "Name": "Small"\n'
                "      }\n"
                "    }\n"
                "  },\n"
                '  "MatchCreated": null,\n'
                '  "MatchInitialized": null,\n'
                '  "MatchDestroyed": null,\n'
                '  "MatchEnded": null,\n'
                '  "MatchPaused": null,\n'
                '  "MatchUnpaused": null,\n'
                '  "PodiumStart": null,\n'
                '  "ReplayCreated": null,\n'
                '  "RoundStarted": null,\n'
                '  "StatfeedEvent": null\n'
                "}\n",
            )

    def test_default_path_prefers_obs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_events_json_path("", root / "obs-output", root / ".data"),
                root / "obs-output" / "latest_statsapi_events.json",
            )

    def test_default_path_falls_back_to_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_events_json_path("", None, root / ".data"),
                root / ".data" / "latest_statsapi_events.json",
            )


class LatestEventFilesTests(unittest.TestCase):
    def test_initializes_known_event_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            events_dir = Path(tmp) / "latest_statsapi_events"

            initialize_latest_event_files(events_dir)

            self.assertEqual((events_dir / "UpdateState.json").read_text(encoding="utf-8"), "null\n")
            self.assertEqual((events_dir / "BallHit.json").read_text(encoding="utf-8"), "null\n")
            self.assertEqual((events_dir / "StatfeedEvent.json").read_text(encoding="utf-8"), "null\n")

    def test_writes_latest_message_to_event_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            events_dir = Path(tmp) / "latest_statsapi_events"

            write_latest_event_file(
                events_dir,
                {"Event": "BallHit", "Data": {"Ball": {"PostHitSpeed": 121.24}}},
            )
            path = write_latest_event_file(
                events_dir,
                {"Event": "BallHit", "Data": {"Ball": {"PostHitSpeed": 132.4}}},
            )

            self.assertEqual(path, events_dir / "BallHit.json")
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                '{\n'
                '  "Event": "BallHit",\n'
                '  "Data": {\n'
                '    "Ball": {\n'
                '      "PostHitSpeed": 132.4\n'
                "    }\n"
                "  }\n"
                "}\n",
            )

    def test_sanitizes_event_file_names(self):
        self.assertEqual(safe_event_filename("Goal Replay/Start?"), "Goal_Replay_Start_")
        self.assertEqual(safe_event_filename(""), "Unknown")

    def test_default_path_prefers_obs_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_events_dir_path("", root / "obs-output", root / ".data"),
                root / "obs-output" / "latest_statsapi_events",
            )

    def test_default_path_falls_back_to_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(
                resolve_latest_events_dir_path("", None, root / ".data"),
                root / ".data" / "latest_statsapi_events",
            )


if __name__ == "__main__":
    unittest.main()
