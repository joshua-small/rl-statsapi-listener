import tempfile
import unittest
from pathlib import Path

from rl_statsapi_listener.cli import initialize_replay_last_goal_file, update_obs_files


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


if __name__ == "__main__":
    unittest.main()
