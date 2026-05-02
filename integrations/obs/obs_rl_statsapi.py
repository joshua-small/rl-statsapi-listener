import json
import socket
import threading
import time
from datetime import datetime

import obspython as obs  # pyright: ignore[reportMissingImports]


# OBS-configurable settings
host = "127.0.0.1"
port = 49123
clock_source = "RL Clock"
blue_score_source = "RL Blue Score"
orange_score_source = "RL Orange Score"
event_source = "RL Event"
status_source = "RL Status"

# Runtime state
_running = False
_thread = None
_state_lock = threading.Lock()
_socket_timeout = 1.0

state: dict[str, str] = {
    "clock": "0:00",
    "blue_score": "0",
    "orange_score": "0",
    "event": "Waiting for match...",
    "status": "Disconnected",
}

team_style: dict[str, dict[str, str | None]] = {
    "blue": {"text": None, "bg": None},
    "orange": {"text": None, "bg": None},
}

last_applied: dict[str, str | None] = {
    "clock": None,
    "blue_score": None,
    "orange_score": None,
    "event": None,
    "status": None,
}

last_applied_team_style: dict[str, dict[str, str | None]] = {
    "blue": {"text": None, "bg": None},
    "orange": {"text": None, "bg": None},
}


def script_description():
    return (
        "Rocket League StatsAPI -> OBS Text Sources\n\n"
        "Create Text sources in OBS and set their names in this script. "
        "The script connects to StatsAPI and updates clock, scores, and event text in real time."
    )


def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(props, "host", "Host", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_int(props, "port", "Port", 1, 65535, 1)

    obs.obs_properties_add_text(props, "clock_source", "Clock Source Name", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "blue_score_source", "Blue Score Source Name", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "orange_score_source", "Orange Score Source Name", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "event_source", "Event Source Name", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_text(props, "status_source", "Status Source Name", obs.OBS_TEXT_DEFAULT)

    return props


def script_defaults(settings):
    obs.obs_data_set_default_string(settings, "host", "127.0.0.1")
    obs.obs_data_set_default_int(settings, "port", 49123)

    obs.obs_data_set_default_string(settings, "clock_source", "RL Clock")
    obs.obs_data_set_default_string(settings, "blue_score_source", "RL Blue Score")
    obs.obs_data_set_default_string(settings, "orange_score_source", "RL Orange Score")
    obs.obs_data_set_default_string(settings, "event_source", "RL Event")
    obs.obs_data_set_default_string(settings, "status_source", "RL Status")


def script_update(settings):
    global host, port
    global clock_source, blue_score_source, orange_score_source, event_source, status_source

    host = obs.obs_data_get_string(settings, "host")
    port = obs.obs_data_get_int(settings, "port")

    clock_source = obs.obs_data_get_string(settings, "clock_source")
    blue_score_source = obs.obs_data_get_string(settings, "blue_score_source")
    orange_score_source = obs.obs_data_get_string(settings, "orange_score_source")
    event_source = obs.obs_data_get_string(settings, "event_source")
    status_source = obs.obs_data_get_string(settings, "status_source")


def script_load(settings):
    global _running, _thread

    # Ensure scores are initialized even before the first packet arrives.
    _set_state("blue_score", "0")
    _set_state("orange_score", "0")

    _running = True
    _thread = threading.Thread(target=_listener_thread, daemon=True)
    _thread.start()

    # Push source updates at 10 Hz.
    obs.timer_add(_apply_state_to_obs, 100)


def script_unload():
    global _running

    _running = False
    obs.timer_remove(_apply_state_to_obs)


def _set_state(key, value):
    with _state_lock:
        state[key] = value


def _set_text_source(source_name, value):
    if not source_name:
        return False

    source = obs.obs_get_source_by_name(source_name)
    if source is None:
        return False

    settings = obs.obs_data_create()
    obs.obs_data_set_string(settings, "text", value)
    obs.obs_source_update(source, settings)
    obs.obs_data_release(settings)
    obs.obs_source_release(source)
    return True


def _normalize_hex_color(value):
    if not isinstance(value, str):
        return None

    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)

    if len(text) != 6:
        return None

    try:
        int(text, 16)
    except ValueError:
        return None

    return text.upper()


def _hex_to_obs_color(hex_rgb):
    """Convert RRGGBB to OBS ARGB integer format used by text sources."""
    rgb = int(hex_rgb, 16)
    r = (rgb >> 16) & 0xFF
    g = (rgb >> 8) & 0xFF
    b = rgb & 0xFF
    return 0xFF000000 | (b << 16) | (g << 8) | r


def _set_team_style(team_name, text_hex, bg_hex):
    with _state_lock:
        team_style[team_name]["text"] = _normalize_hex_color(text_hex)
        team_style[team_name]["bg"] = _normalize_hex_color(bg_hex)


def _apply_score_source_style(source_name, style):
    if not source_name:
        return False

    text_hex = style.get("text")
    bg_hex = style.get("bg")
    if text_hex is None and bg_hex is None:
        return False

    source = obs.obs_get_source_by_name(source_name)
    if source is None:
        return False

    source_id = obs.obs_source_get_id(source)
    settings = obs.obs_data_create()

    if text_hex is not None:
        text_color = _hex_to_obs_color(text_hex)
    else:
        text_color = None

    if bg_hex is not None:
        bg_color = _hex_to_obs_color(bg_hex)
    else:
        bg_color = None

    # Windows Text (GDI+) supports explicit background color.
    if source_id == "text_gdiplus":
        if text_color is not None:
            obs.obs_data_set_int(settings, "color", text_color)
        if bg_color is not None:
            obs.obs_data_set_int(settings, "bk_color", bg_color)
            obs.obs_data_set_int(settings, "bk_opacity", 100)
    # Linux/macOS Text (FreeType2) supports text color but no reliable background fill.
    elif source_id == "text_ft2_source":
        if text_color is not None:
            obs.obs_data_set_int(settings, "color1", text_color)
            obs.obs_data_set_int(settings, "color2", text_color)
    else:
        obs.obs_data_release(settings)
        obs.obs_source_release(source)
        return False

    obs.obs_source_update(source, settings)
    obs.obs_data_release(settings)
    obs.obs_source_release(source)
    return True


def _apply_state_to_obs():
    with _state_lock:
        snapshot = dict(state)
        style_snapshot = {
            "blue": dict(team_style["blue"]),
            "orange": dict(team_style["orange"]),
        }

    mapping = [
        ("clock", clock_source),
        ("blue_score", blue_score_source),
        ("orange_score", orange_score_source),
        ("event", event_source),
        ("status", status_source),
    ]

    for key, source_name in mapping:
        value = snapshot.get(key, "")
        if last_applied.get(key) != value:
            if _set_text_source(source_name, value):
                last_applied[key] = value

    score_style_mapping = [
        ("blue", blue_score_source),
        ("orange", orange_score_source),
    ]
    for team_name, source_name in score_style_mapping:
        style = style_snapshot[team_name]
        if last_applied_team_style[team_name] != style:
            if _apply_score_source_style(source_name, style):
                last_applied_team_style[team_name] = dict(style)


def _safe_parse_data(message):
    data = message.get("Data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            pass
    return data if isinstance(data, dict) else {}


def _format_clock(time_seconds, overtime):
    if not isinstance(time_seconds, int):
        return None

    t = max(0, time_seconds)
    m = t // 60
    s = t % 60
    text = f"{m}:{s:02d}"
    if overtime:
        text = f"OT {text}"
    return text


def _handle_message(message):
    event = message.get("Event", "Unknown")
    data = _safe_parse_data(message)

    _set_state("status", f"Connected {datetime.now().strftime('%H:%M:%S')}")

    if event == "UpdateState":
        game = data.get("Game", {})
        if isinstance(game, dict):
            clock = _format_clock(game.get("TimeSeconds"), game.get("bOvertime", False))
            if clock is not None:
                _set_state("clock", clock)

            teams = game.get("Teams", [])
            if isinstance(teams, list):
                for team in teams:
                    if not isinstance(team, dict):
                        continue
                    team_num = team.get("TeamNum")
                    score = team.get("Score")
                    # Requested mapping:
                    # background <- ColorPrimary, text <- ColorSecondary
                    color_bg = team.get("ColorPrimary")
                    color_text = team.get("ColorSecondary")
                    if score is None:
                        score = 0
                    if team_num == 0:
                        _set_state("blue_score", str(score))
                        _set_team_style("blue", color_text, color_bg)
                    elif team_num == 1:
                        _set_state("orange_score", str(score))
                        _set_team_style("orange", color_text, color_bg)

    elif event == "ClockUpdatedSeconds":
        clock = _format_clock(data.get("TimeSeconds"), data.get("bOvertime", False))
        if clock is not None:
            _set_state("clock", clock)

    elif event == "GoalScored":
        scorer = data.get("Scorer", {})
        if isinstance(scorer, dict):
            name = scorer.get("Name", "Unknown")
        else:
            name = "Unknown"
        _set_state("event", f"GOAL: {name}")

    elif event == "MatchEnded":
        winner = data.get("WinnerTeamNum")
        if winner == 0:
            _set_state("event", "MATCH ENDED - BLUE WIN")
        elif winner == 1:
            _set_state("event", "MATCH ENDED - ORANGE WIN")
        else:
            _set_state("event", "MATCH ENDED")

    elif event == "RoundStarted":
        _set_state("event", "ROUND START")


def _decode_messages(buffer, decoder):
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
            return buffer[cursor:], messages

        messages.append(obj)
        cursor = next_cursor

    return "", messages


def _listener_thread():
    decoder = json.JSONDecoder()

    while _running:
        try:
            _set_state("status", f"Connecting to {host}:{port}")
            with socket.create_connection((host, port), timeout=3.0) as sock:
                sock.settimeout(_socket_timeout)
                _set_state("status", f"Connected to {host}:{port}")
                buffer = ""

                while _running:
                    try:
                        chunk = sock.recv(65536)
                        if not chunk:
                            _set_state("status", "Disconnected (server closed)")
                            break
                    except socket.timeout:
                        continue

                    text = chunk.decode("utf-8", errors="replace")
                    buffer += text
                    buffer, messages = _decode_messages(buffer, decoder)

                    for msg in messages:
                        if isinstance(msg, dict):
                            _handle_message(msg)
        except Exception as exc:
            _set_state("status", f"Reconnect in 2s ({exc})")
            if _running:
                time.sleep(2)
