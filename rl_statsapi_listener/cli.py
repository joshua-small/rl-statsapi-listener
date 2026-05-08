import argparse
import json
import socket
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .overlay_state import OverlayStatsTracker, StatsStore
from .web_overlay_server import start_web_overlay_server


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 49123
DEFAULT_LATEST_FRAME_JSON = "latest_statsapi_frame.json"
DEFAULT_LATEST_EVENTS_JSON = "latest_statsapi_events.json"
DEFAULT_LATEST_EVENTS_DIR = "latest_statsapi_events"
REPLAY_LAST_GOAL_DEFAULT = "-- kph"
REPLAY_SPEED_WINDOW_SECONDS = 6.0
REPLAY_SPEED_WINDOW_FRAMES = 720
TRACKED_STATSAPI_EVENTS = (
    "UpdateState",
    "BallHit",
    "ClockUpdatedSeconds",
    "CountdownBegin",
    "CrossbarHit",
    "GoalReplayEnd",
    "GoalReplayStart",
    "GoalReplayWillEnd",
    "GoalScored",
    "MatchCreated",
    "MatchInitialized",
    "MatchDestroyed",
    "MatchEnded",
    "MatchPaused",
    "MatchUnpaused",
    "PodiumStart",
    "ReplayCreated",
    "RoundStarted",
    "StatfeedEvent",
)
REPLAY_GOAL_SPEED_FIELDS = (
    "goalSpeed",
    "GoalSpeed",
    "shotSpeed",
    "ShotSpeed",
    "ballSpeed",
    "BallSpeed",
    "PostHitSpeed",
    "postHitSpeed",
    "speed",
    "Speed",
)
BALL_SPEED_FIELDS = (
    "PostHitSpeed",
    "postHitSpeed",
    "GoalSpeed",
    "goalSpeed",
    "BallSpeed",
    "ballSpeed",
    "Speed",
    "speed",
)
PLAYER_ID_FIELDS = (
    "PrimaryId",
    "primaryId",
    "UniqueId",
    "UniqueID",
    "uniqueId",
    "UniqueNetId",
    "OnlineID",
    "OnlineId",
    "PlatformId",
    "platformId",
    "EpicAccountId",
    "PlayerID",
)
PLAYER_CONTAINERS = (
    "Scorer",
    "scorer",
    "Player",
    "player",
    "LastTouch",
    "lastTouch",
    "HitPlayer",
    "hitPlayer",
    "Instigator",
    "instigator",
)


def parse_data_field(message: dict) -> dict:
    data = message.get("Data", {})
    if isinstance(data, str):
        try:
            parsed_data = json.loads(data)
            data = parsed_data
        except json.JSONDecodeError:
            pass
    return data if isinstance(data, dict) else {"value": data}


def write_text_if_changed(path: Path, value: str, cache: dict):
    if cache.get(path) == value:
        return
    path.write_text(value, encoding="utf-8")
    cache[path] = value


def write_latest_frame_json(path: Path, message: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(message, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def initialize_latest_events_by_type() -> dict[str, dict | None]:
    return {event: None for event in TRACKED_STATSAPI_EVENTS}


def update_latest_events_by_type(events_by_type: dict[str, dict | None], message: dict) -> None:
    event = as_text(message.get("Event")) or "Unknown"
    events_by_type[event] = message


def write_latest_events_json(path: Path, events_by_type: dict[str, dict | None]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events_by_type, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def initialize_latest_event_files(events_dir: Path) -> None:
    events_dir.mkdir(parents=True, exist_ok=True)
    for event in TRACKED_STATSAPI_EVENTS:
        write_latest_event_value(events_dir, event, None)


def write_latest_event_file(events_dir: Path, message: dict) -> Path:
    event = as_text(message.get("Event")) or "Unknown"
    return write_latest_event_value(events_dir, event, message)


def write_latest_event_value(events_dir: Path, event: str, value: dict | None) -> Path:
    path = events_dir / f"{safe_event_filename(event)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def safe_event_filename(event: str) -> str:
    text = event.strip()
    safe = []
    for char in text:
        if char.isascii() and (char.isalnum() or char in {"_", "-"}):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "Unknown"


def resolve_latest_frame_json_path(value: str | None, obs_dir: Path | None, data_dir: Path) -> Path | None:
    if value is None:
        return None
    if value:
        return Path(value).expanduser().resolve()
    if obs_dir is not None:
        return obs_dir / DEFAULT_LATEST_FRAME_JSON
    return data_dir / DEFAULT_LATEST_FRAME_JSON


def resolve_latest_events_json_path(value: str | None, obs_dir: Path | None, data_dir: Path) -> Path | None:
    if value is None:
        return None
    if value:
        return Path(value).expanduser().resolve()
    if obs_dir is not None:
        return obs_dir / DEFAULT_LATEST_EVENTS_JSON
    return data_dir / DEFAULT_LATEST_EVENTS_JSON


def resolve_latest_events_dir_path(value: str | None, obs_dir: Path | None, data_dir: Path) -> Path | None:
    if value is None:
        return None
    if value:
        return Path(value).expanduser().resolve()
    if obs_dir is not None:
        return obs_dir / DEFAULT_LATEST_EVENTS_DIR
    return data_dir / DEFAULT_LATEST_EVENTS_DIR


def update_obs_files(
    message: dict,
    obs_dir: Path,
    cache: dict,
    replay_goal_player_id: str | None = None,
    replay_goal_state: dict[str, Any] | None = None,
):
    event = message.get("Event", "Unknown")
    data = parse_data_field(message)

    write_text_if_changed(obs_dir / "event_name.txt", str(event), cache)
    if replay_goal_state is not None:
        update_replay_last_goal_file(
            str(event),
            data,
            obs_dir,
            cache,
            replay_goal_state,
            replay_goal_player_id,
        )

    if event == "UpdateState":
        game = data.get("Game", {})
        if isinstance(game, dict):
            time_seconds = game.get("TimeSeconds")
            overtime = game.get("bOvertime", False)
            if isinstance(time_seconds, int):
                minutes = max(0, time_seconds) // 60
                seconds = max(0, time_seconds) % 60
                clock = f"{minutes}:{seconds:02d}"
                if overtime:
                    clock = f"OT {clock}"
                write_text_if_changed(obs_dir / "clock.txt", clock, cache)

            teams = game.get("Teams", [])
            if isinstance(teams, list):
                blue_score = "0"
                orange_score = "0"
                for team in teams:
                    if not isinstance(team, dict):
                        continue
                    team_num = team.get("TeamNum")
                    score = team.get("Score")
                    if team_num == 0 and score is not None:
                        blue_score = str(score)
                    elif team_num == 1 and score is not None:
                        orange_score = str(score)
                write_text_if_changed(obs_dir / "score_blue.txt", blue_score, cache)
                write_text_if_changed(obs_dir / "score_orange.txt", orange_score, cache)

    elif event == "ClockUpdatedSeconds":
        time_seconds = data.get("TimeSeconds")
        overtime = data.get("bOvertime", False)
        if isinstance(time_seconds, int):
            minutes = max(0, time_seconds) // 60
            seconds = max(0, time_seconds) % 60
            clock = f"{minutes}:{seconds:02d}"
            if overtime:
                clock = f"OT {clock}"
            write_text_if_changed(obs_dir / "clock.txt", clock, cache)

    elif event == "GoalScored":
        scorer = data.get("Scorer", {})
        scorer_name = "Unknown"
        if isinstance(scorer, dict):
            scorer_name = str(scorer.get("Name", "Unknown"))
        write_text_if_changed(obs_dir / "event_banner.txt", f"GOAL: {scorer_name}", cache)

    elif event == "MatchEnded":
        winner_team = data.get("WinnerTeamNum")
        if winner_team == 0:
            banner = "MATCH ENDED - BLUE WIN"
        elif winner_team == 1:
            banner = "MATCH ENDED - ORANGE WIN"
        else:
            banner = "MATCH ENDED"
        write_text_if_changed(obs_dir / "event_banner.txt", banner, cache)


def initialize_replay_last_goal_file(obs_dir: Path, cache: dict) -> None:
    write_text_if_changed(obs_dir / "replay_last_goal.txt", REPLAY_LAST_GOAL_DEFAULT, cache)


def update_replay_last_goal_file(
    event: str,
    data: dict[str, Any],
    obs_dir: Path,
    cache: dict,
    state: dict[str, Any],
    replay_goal_player_id: str | None = None,
) -> None:
    if event == "UpdateState":
        update_replay_goal_from_update_state(data, obs_dir, cache, state)
        return

    if event == "BallHit":
        speed = extract_replay_goal_speed_kph(data)
        if speed is None:
            return
        state["last_ball_hit_speed_kph"] = speed

        player_id = extract_event_player_id(data)
        if player_id:
            state["last_ball_hit_player_id"] = player_id
            by_player = state.setdefault("last_ball_hit_by_player", {})
            by_player[normalize_player_id(player_id)] = speed
        return

    if event != "GoalScored":
        return

    target_id = normalize_player_id(replay_goal_player_id) if replay_goal_player_id else None
    scorer_id = extract_event_player_id(data)
    scorer_key = normalize_player_id(scorer_id) if scorer_id else None
    last_hit_key = normalize_player_id(state.get("last_ball_hit_player_id"))
    by_player = state.setdefault("last_ball_hit_by_player", {})

    if target_id:
        if scorer_key and scorer_key != target_id:
            return
        if not scorer_key and last_hit_key != target_id:
            return

    speed = extract_replay_goal_speed_kph(data)
    if speed is None and scorer_key:
        speed = by_player.get(scorer_key)
    if speed is None and target_id:
        speed = by_player.get(target_id)
    if speed is None:
        speed = state.get("last_ball_hit_speed_kph")

    write_text_if_changed(obs_dir / "replay_last_goal.txt", format_speed_kph(speed), cache)


def update_replay_goal_from_update_state(
    data: dict[str, Any],
    obs_dir: Path,
    cache: dict,
    state: dict[str, Any],
) -> None:
    game = data.get("Game")
    if not isinstance(game, dict):
        return

    match_guid = as_text(data.get("MatchGuid") or game.get("MatchGuid"))
    if match_guid and state.get("update_state_match_guid") != match_guid:
        state["update_state_match_guid"] = match_guid
        state.pop("last_update_team_scores", None)
        state["recent_update_ball_speeds"] = []

    elapsed = to_float(game.get("Elapsed"))
    frame = to_float(game.get("Frame"))
    ball_speed = extract_update_state_ball_speed_kph(game, data)
    if ball_speed is not None:
        state["last_update_ball_speed_kph"] = ball_speed
        if ball_speed > 0:
            recent = state.setdefault("recent_update_ball_speeds", [])
            recent.append({"speed": ball_speed, "elapsed": elapsed, "frame": frame})
            prune_recent_update_ball_speeds(recent, elapsed, frame)

    scores = extract_update_state_scores(game)
    if not scores:
        return

    previous_scores = state.get("last_update_team_scores")
    if isinstance(previous_scores, dict):
        if score_decreased(previous_scores, scores):
            state["recent_update_ball_speeds"] = []
        elif score_increased(previous_scores, scores):
            speed = best_recent_update_ball_speed(state, elapsed, frame)
            if speed is None or speed <= 0:
                speed = state.get("last_update_ball_speed_kph")
            write_text_if_changed(obs_dir / "replay_last_goal.txt", format_speed_kph(to_float(speed)), cache)
            state["recent_update_ball_speeds"] = []

    state["last_update_team_scores"] = scores


def extract_update_state_ball_speed_kph(game: dict[str, Any], data: dict[str, Any]) -> float | None:
    ball = game.get("Ball")
    if not isinstance(ball, dict):
        return None
    speed = first_numeric_value(ball, BALL_SPEED_FIELDS)
    if speed is None:
        return None
    return convert_speed_to_kph(speed, ball, game, data)


def extract_update_state_scores(game: dict[str, Any]) -> dict[int, int]:
    teams = game.get("Teams")
    if not isinstance(teams, list):
        return {}

    scores = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_num = to_int(team.get("TeamNum"))
        score = to_int(team.get("Score"))
        if team_num is not None and score is not None:
            scores[team_num] = score
    return scores


def prune_recent_update_ball_speeds(
    recent: list[dict[str, float | None]],
    elapsed: float | None,
    frame: float | None,
) -> None:
    if elapsed is not None:
        cutoff = elapsed - REPLAY_SPEED_WINDOW_SECONDS
        recent[:] = [sample for sample in recent if sample.get("elapsed") is None or sample["elapsed"] >= cutoff]
        return

    if frame is not None:
        cutoff = frame - REPLAY_SPEED_WINDOW_FRAMES
        recent[:] = [sample for sample in recent if sample.get("frame") is None or sample["frame"] >= cutoff]


def best_recent_update_ball_speed(state: dict[str, Any], elapsed: float | None, frame: float | None) -> float | None:
    recent = state.get("recent_update_ball_speeds")
    if not isinstance(recent, list):
        return None

    if elapsed is not None or frame is not None:
        prune_recent_update_ball_speeds(recent, elapsed, frame)

    speeds = [to_float(sample.get("speed")) for sample in recent if isinstance(sample, dict)]
    speeds = [speed for speed in speeds if speed is not None]
    return max(speeds) if speeds else None


def score_increased(previous_scores: dict[int, int], scores: dict[int, int]) -> bool:
    for team_num, score in scores.items():
        previous = previous_scores.get(team_num)
        if previous is not None and score > previous:
            return True
    return False


def score_decreased(previous_scores: dict[int, int], scores: dict[int, int]) -> bool:
    for team_num, score in scores.items():
        previous = previous_scores.get(team_num)
        if previous is not None and score < previous:
            return True
    return False


def extract_replay_goal_speed_kph(data: dict[str, Any]) -> float | None:
    ball = find_first_key(data, ("Ball", "ball"))
    if isinstance(ball, dict):
        ball_speed = first_numeric_value(ball, BALL_SPEED_FIELDS)
        if ball_speed is not None:
            return convert_speed_to_kph(ball_speed, ball, data)

    speed = first_numeric_value(data, REPLAY_GOAL_SPEED_FIELDS)
    if speed is None:
        return None
    return convert_speed_to_kph(speed, data)


def first_numeric_value(value: Any, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        number = to_float(find_first_key(value, (key,)))
        if number is not None:
            return number
    return None


def convert_speed_to_kph(speed: float, *unit_sources: dict[str, Any]) -> float:
    unit = None
    for source in unit_sources:
        unit = normalize_token(find_first_key(source, ("unit", "Unit", "speedUnit", "SpeedUnit")))
        if unit:
            break
    if unit in {"mph", "mi/h"}:
        return speed * 1.609344
    return speed


def extract_event_player_id(data: dict[str, Any]) -> str | None:
    for container_name in PLAYER_CONTAINERS:
        player = data.get(container_name)
        if isinstance(player, dict):
            player_id = extract_player_id(player)
            if player_id:
                return player_id

    return extract_player_id(data)


def extract_player_id(player: dict[str, Any]) -> str | None:
    for key in PLAYER_ID_FIELDS:
        value = as_text(player.get(key))
        if value:
            return value

    platform = player.get("Platform")
    if isinstance(platform, dict):
        for key in ("PlatformId", "Id", "ID", "OnlineID"):
            value = as_text(platform.get(key))
            if value:
                return value
    return None


def find_first_key(value: Any, keys: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return value[key]
        for child in value.values():
            found = find_first_key(child, keys, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_first_key(child, keys, depth + 1)
            if found is not None:
                return found
    return None


def normalize_player_id(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip().lower()


def normalize_token(value: Any) -> str | None:
    text = as_text(value)
    if text is None:
        return None
    text = text.strip().lower()
    return text or None


def as_text(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def to_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def format_speed_kph(speed: float | None) -> str:
    if speed is None:
        return REPLAY_LAST_GOAL_DEFAULT
    if speed.is_integer():
        return f"{int(speed)} kph"
    return f"{speed:.1f} kph"


def format_event_summary(message: dict) -> str:
    event = message.get("Event", "<UnknownEvent>")
    data = parse_data_field(message)

    match_guid = data.get("MatchGuid", "-")

    extras = []
    if event == "UpdateState":
        game = data.get("Game", {})
        if not isinstance(game, dict):
            game = {}
        extras.append(f"time={game.get('TimeSeconds', '?')}")
        extras.append(f"ot={game.get('bOvertime', False)}")
    elif event == "GoalScored":
        scorer_info = data.get("Scorer", {})
        scorer = scorer_info.get("Name", "?") if isinstance(scorer_info, dict) else "?"
        extras.append(f"scorer={scorer}")
    elif event == "BallHit":
        ball = data.get("Ball", {})
        if not isinstance(ball, dict):
            ball = {}
        extras.append(f"speed={ball.get('PostHitSpeed', '?')}")

    extras_text = f" ({', '.join(extras)})" if extras else ""
    return f"Event={event} MatchGuid={match_guid}{extras_text}"


def process_buffer(buffer: str, decoder: json.JSONDecoder):
    """Decode as many full JSON objects as possible from a TCP text buffer."""
    messages = []
    cursor = 0
    n = len(buffer)

    while cursor < n:
        while cursor < n and buffer[cursor].isspace():
            cursor += 1

        if cursor >= n:
            return "", messages

        try:
            obj, next_cursor = decoder.raw_decode(buffer, cursor)
        except json.JSONDecodeError:
            # Incomplete payload: keep remaining text for the next recv.
            return buffer[cursor:], messages

        messages.append(obj)
        cursor = next_cursor

    return "", messages


def main():
    parser = argparse.ArgumentParser(description="Listen to Rocket League StatsAPI socket stream")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Socket host (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Socket port (default: {DEFAULT_PORT})")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print full JSON messages instead of one-line summaries",
    )
    parser.add_argument(
        "--raw-chunks",
        action="store_true",
        help="Also print raw incoming chunks for transport-level debugging",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-event console summaries while still updating outputs",
    )
    parser.add_argument(
        "--latest-frame-json",
        nargs="?",
        const="",
        metavar="PATH",
        help=(
            "Continuously write the latest decoded StatsAPI message as pretty JSON. "
            "Without PATH, writes latest_statsapi_frame.json in --obs-dir or --data-dir."
        ),
    )
    parser.add_argument(
        "--latest-events-json",
        nargs="?",
        const="",
        metavar="PATH",
        help=(
            "Continuously write the latest decoded StatsAPI message for each event type as pretty JSON. "
            "Without PATH, writes latest_statsapi_events.json in --obs-dir or --data-dir."
        ),
    )
    parser.add_argument(
        "--latest-events-dir",
        nargs="?",
        const="",
        metavar="DIR",
        help=(
            "Continuously write one pretty JSON file per StatsAPI event type. "
            "Without DIR, writes files under latest_statsapi_events/ in --obs-dir or --data-dir."
        ),
    )
    parser.add_argument(
        "--obs-dir",
        help="Directory to write OBS-friendly text files (clock/score/event)",
    )
    parser.add_argument(
        "--replay-last-goal",
        action="store_true",
        help="Write replay_last_goal.txt with the latest replay/match goal speed",
    )
    parser.add_argument(
        "--replay-goal-player-id",
        help="Only update replay_last_goal.txt for this scorer/player PrimaryId or UniqueId",
    )
    parser.add_argument(
        "--data-dir",
        default=".data",
        help="Directory containing captured player/club/dejavu snapshots (default: .data)",
    )
    parser.add_argument(
        "--stats-db",
        default=".data/rl_stats.sqlite3",
        help="SQLite database for overlay stats state (default: .data/rl_stats.sqlite3)",
    )
    parser.add_argument(
        "--no-overlay-stats",
        action="store_true",
        help="Disable SQLite-backed session/lifetime/dejavu/freeplay tracking",
    )
    parser.add_argument(
        "--reimport-snapshots",
        action="store_true",
        help="Re-read snapshot files in --data-dir before listening",
    )
    parser.add_argument(
        "--web-overlay",
        action="store_true",
        help="Serve the HTML/CSS/JS overlay at http://127.0.0.1:8765/ while listening",
    )
    parser.add_argument(
        "--web-host",
        default="127.0.0.1",
        help="Host for --web-overlay (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8765,
        help="Port for --web-overlay (default: 8765)",
    )
    args = parser.parse_args()

    buffer = ""
    decoder = json.JSONDecoder()
    message_count = 0
    obs_dir = None
    obs_cache = {}
    replay_goal_state = None
    stats_store = None
    stats_tracker = None
    stats_lock = threading.RLock()
    web_server = None
    data_dir = Path(args.data_dir).expanduser().resolve()
    latest_frame_json_path = None
    latest_events_json_path = None
    latest_events_dir_path = None
    latest_events_by_type = initialize_latest_events_by_type()

    if args.obs_dir:
        obs_dir = Path(args.obs_dir).expanduser().resolve()
        obs_dir.mkdir(parents=True, exist_ok=True)
        print(f"OBS output enabled: {obs_dir}")
        if args.replay_last_goal or args.replay_goal_player_id:
            replay_goal_state = {}
            initialize_replay_last_goal_file(obs_dir, obs_cache)
            if args.replay_goal_player_id:
                print(f"Replay last-goal output enabled for player: {args.replay_goal_player_id}")
            else:
                print("Replay last-goal output enabled for all scorers")

    latest_frame_json_path = resolve_latest_frame_json_path(args.latest_frame_json, obs_dir, data_dir)
    if latest_frame_json_path is not None:
        print(f"Latest StatsAPI frame JSON enabled: {latest_frame_json_path}")

    latest_events_json_path = resolve_latest_events_json_path(args.latest_events_json, obs_dir, data_dir)
    if latest_events_json_path is not None:
        write_latest_events_json(latest_events_json_path, latest_events_by_type)
        print(f"Latest StatsAPI events JSON enabled: {latest_events_json_path}")

    latest_events_dir_path = resolve_latest_events_dir_path(args.latest_events_dir, obs_dir, data_dir)
    if latest_events_dir_path is not None:
        initialize_latest_event_files(latest_events_dir_path)
        print(f"Latest StatsAPI event files enabled: {latest_events_dir_path}")

    if not args.no_overlay_stats:
        stats_db = Path(args.stats_db).expanduser().resolve()
        stats_store = StatsStore(stats_db, data_dir)
        try:
            stats_store.initialize(reimport_snapshots=args.reimport_snapshots)
            stats_tracker = OverlayStatsTracker(stats_store, obs_dir=obs_dir)
            print(f"Overlay stats database enabled: {stats_db}")
        except Exception as exc:
            stats_store.close()
            stats_store = None
            print(f"Overlay stats disabled: {exc}")

    if args.web_overlay:
        if stats_tracker is None:
            print("Web overlay disabled: overlay stats are unavailable")
        else:
            try:
                web_server, _web_thread = start_web_overlay_server(
                    args.web_host,
                    args.web_port,
                    lambda: _snapshot_tracker(stats_tracker, stats_lock),
                    data_dir=data_dir,
                )
                print(f"Web overlay enabled: http://{args.web_host}:{args.web_port}/")
            except OSError as exc:
                print(f"Web overlay disabled: {exc}")

    print(f"Connecting to {args.host}:{args.port}...")
    try:
        with socket.create_connection((args.host, args.port)) as sock:
            print("Connected. Waiting for StatsAPI data...\\n")

            while True:
                chunk = sock.recv(65536)
                if not chunk:
                    print("Connection closed by server.")
                    break

                text = chunk.decode("utf-8", errors="replace")
                if args.raw_chunks:
                    print("--- RAW CHUNK START ---")
                    print(text.rstrip())
                    print("--- RAW CHUNK END ---")

                buffer += text
                buffer, messages = process_buffer(buffer, decoder)

                for message in messages:
                    message_count += 1
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                    if not isinstance(message, dict):
                        print(f"[{ts}] #{message_count} Non-object payload: {repr(message)[:200]}")
                        continue

                    # Normalize Data when received as stringified JSON.
                    if isinstance(message.get("Data"), str):
                        try:
                            message["Data"] = json.loads(message["Data"])
                        except json.JSONDecodeError:
                            pass

                    if latest_frame_json_path is not None:
                        write_latest_frame_json(latest_frame_json_path, message)

                    if latest_events_json_path is not None:
                        update_latest_events_by_type(latest_events_by_type, message)
                        write_latest_events_json(latest_events_json_path, latest_events_by_type)

                    if latest_events_dir_path is not None:
                        write_latest_event_file(latest_events_dir_path, message)

                    if obs_dir is not None:
                        update_obs_files(
                            message,
                            obs_dir,
                            obs_cache,
                            replay_goal_player_id=args.replay_goal_player_id,
                            replay_goal_state=replay_goal_state,
                        )

                    if stats_tracker is not None:
                        try:
                            with stats_lock:
                                stats_tracker.handle_message(message)
                        except Exception as exc:
                            print(f"[{ts}] #{message_count} Overlay stats error: {exc}")

                    if args.pretty:
                        print(f"[{ts}] #{message_count}")
                        print(json.dumps(message, indent=2, ensure_ascii=True))
                    elif not args.quiet:
                        print(f"[{ts}] #{message_count} {format_event_summary(message)}")
    except KeyboardInterrupt:
        print("\nListener stopped by user.")
    finally:
        if web_server is not None:
            web_server.shutdown()
            web_server.server_close()
        if stats_store is not None:
            stats_store.close()


def _snapshot_tracker(stats_tracker: OverlayStatsTracker, stats_lock: threading.RLock) -> dict:
    with stats_lock:
        return stats_tracker.get_overlay_state()


if __name__ == "__main__":
    main()
