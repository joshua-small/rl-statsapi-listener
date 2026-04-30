import argparse
import json
import socket
from datetime import datetime
from pathlib import Path

from .overlay_state import OverlayStatsTracker, StatsStore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 49123


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


def update_obs_files(message: dict, obs_dir: Path, cache: dict):
    event = message.get("Event", "Unknown")
    data = parse_data_field(message)

    write_text_if_changed(obs_dir / "event_name.txt", str(event), cache)

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
        "--obs-dir",
        help="Directory to write OBS-friendly text files (clock/score/event)",
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
    args = parser.parse_args()

    buffer = ""
    decoder = json.JSONDecoder()
    message_count = 0
    obs_dir = None
    obs_cache = {}
    stats_store = None
    stats_tracker = None

    if args.obs_dir:
        obs_dir = Path(args.obs_dir).expanduser().resolve()
        obs_dir.mkdir(parents=True, exist_ok=True)
        print(f"OBS output enabled: {obs_dir}")

    if not args.no_overlay_stats:
        data_dir = Path(args.data_dir).expanduser().resolve()
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

                    if obs_dir is not None:
                        update_obs_files(message, obs_dir, obs_cache)

                    if stats_tracker is not None:
                        try:
                            stats_tracker.handle_message(message)
                        except Exception as exc:
                            print(f"[{ts}] #{message_count} Overlay stats error: {exc}")

                    if args.pretty:
                        print(f"[{ts}] #{message_count}")
                        print(json.dumps(message, indent=2, ensure_ascii=True))
                    else:
                        print(f"[{ts}] #{message_count} {format_event_summary(message)}")
    except KeyboardInterrupt:
        print("\nListener stopped by user.")
    finally:
        if stats_store is not None:
            stats_store.close()


if __name__ == "__main__":
    main()
