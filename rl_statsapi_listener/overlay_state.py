from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLAYER_YAML = "player.yml"
CLUB_YAML = "club.yml"
CLUB_ROSTER_YAML = "club-roster.yml"
FREEPLAY_GOAL_YAML = "freeplay_goal.yml"
DEJAVU_YAML = "dejavu_player_counter.yml"
LEGACY_DEJAVU_YAML = "dejavu/player_counter.yml"
DEJAVU_JSON_BACKUP = "dejavu/player_counter.json.bak"
FREEPLAY_SPEED_WINDOW_SECONDS = 6.0
FREEPLAY_SPEED_WINDOW_FRAMES = 720
FREEPLAY_GOAL_DEDUPE_SECONDS = 2.5
FREEPLAY_GOAL_DEDUPE_FRAMES = 300
FREEPLAY_GOAL_DEDUPE_MESSAGES = 20
KNOWN_SELF_TOKENS = {
    "76561198080314981",
    "27492b8e1d074bd69f93fefc7c284205",
    "399c852cc7ea4522b9e53f472e9f6f2a",
    "noooo! great pass!",
    "nonono greatpass",
    "noooo great pass",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_data_field(message: dict[str, Any]) -> dict[str, Any]:
    data = message.get("Data", {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            pass
    return data if isinstance(data, dict) else {}


@dataclass(frozen=True)
class YamlLine:
    indent: int
    content: str


def load_yaml_like(path: Path) -> Any:
    """Parse the simple YAML shape used by the captured Rocket League exports."""
    lines: list[YamlLine] = []
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append(YamlLine(indent=indent, content=raw_line.strip()))

    if not lines:
        return {}

    value, index = _parse_yaml_node(lines, 0)
    if index != len(lines):
        raise ValueError(f"Could not parse all of {path}")
    return value


def _parse_yaml_node(lines: list[YamlLine], index: int) -> tuple[Any, int]:
    if lines[index].content.startswith("- "):
        return _parse_yaml_list(lines, index, lines[index].indent)
    return _parse_yaml_dict(lines, index, lines[index].indent)


def _parse_yaml_dict(lines: list[YamlLine], index: int, indent: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}

    while index < len(lines):
        line = lines[index]
        if line.indent < indent:
            break
        if line.indent > indent:
            break
        if line.content.startswith("- "):
            break

        key, value_text = _split_yaml_pair(line.content)
        index += 1

        if value_text == "":
            if index < len(lines) and lines[index].indent > indent:
                value, index = _parse_yaml_node(lines, index)
            else:
                value = {}
        else:
            value = _parse_scalar(value_text)

        result[key] = value

    return result, index


def _parse_yaml_list(lines: list[YamlLine], index: int, indent: int) -> tuple[list[Any], int]:
    result: list[Any] = []

    while index < len(lines):
        line = lines[index]
        if line.indent != indent or not line.content.startswith("- "):
            break

        item_text = line.content[2:].strip()
        index += 1

        if item_text == "":
            if index < len(lines) and lines[index].indent > indent:
                item, index = _parse_yaml_node(lines, index)
            else:
                item = None
        elif ":" in item_text:
            key, value_text = _split_yaml_pair(item_text)
            item = {}
            if value_text == "":
                if index < len(lines) and lines[index].indent > indent:
                    value, index = _parse_yaml_node(lines, index)
                else:
                    value = {}
            else:
                value = _parse_scalar(value_text)
            item[key] = value

            while index < len(lines) and lines[index].indent > indent:
                child, index = _parse_yaml_node(lines, index)
                if isinstance(child, dict):
                    item.update(child)
                else:
                    item.setdefault("items", []).append(child)
        else:
            item = _parse_scalar(item_text)

        result.append(item)

    return result, index


def _split_yaml_pair(text: str) -> tuple[str, str]:
    key, sep, value = text.partition(":")
    if not sep:
        raise ValueError(f"Expected YAML key/value pair: {text!r}")
    return key.strip(), value.strip()


def _parse_scalar(value: str) -> Any:
    if value == "":
        return ""

    lower = value.lower()
    if lower in {"null", "none", "~"}:
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False

    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]

    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            return value

    if re.fullmatch(r"-?(?:\d+\.\d*|\d*\.\d+)", value):
        try:
            return float(value)
        except ValueError:
            return value

    return value


def _flatten(prefix: str, value: Any) -> list[tuple[str, Any]]:
    if not isinstance(value, dict):
        return [(prefix, value)]

    pairs: list[tuple[str, Any]] = []
    for key, child in value.items():
        child_prefix = f"{prefix}.{key}" if prefix else str(key)
        pairs.extend(_flatten(child_prefix, child))
    return pairs


def _to_int(value: Any) -> int | None:
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


def _to_float(value: Any) -> float | None:
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


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        for key in ("id", "Id", "ID", "uid", "UniqueId", "UniqueID", "PlatformId", "OnlineID"):
            if key in value:
                return _as_text(value[key])
        return json.dumps(value, sort_keys=True)
    return str(value)


class StatsStore:
    def __init__(self, db_path: Path, data_dir: Path):
        self.db_path = Path(db_path)
        self.data_dir = Path(data_dir)
        self.conn: sqlite3.Connection | None = None

    def initialize(self, reimport_snapshots: bool = False) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # The web overlay server reads snapshots from a background HTTP thread.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

        if reimport_snapshots or not self.get_meta("snapshots_imported_at"):
            self.import_snapshots()

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _db(self) -> sqlite3.Connection:
        if self.conn is None:
            raise RuntimeError("StatsStore is not initialized")
        return self.conn

    def _create_schema(self) -> None:
        db = self._db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                platform TEXT,
                platform_id TEXT,
                display_name TEXT,
                captured_at TEXT
            );

            CREATE TABLE IF NOT EXISTS playlist_mmr (
                playlist_id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                value REAL,
                updated_at TEXT,
                source TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS career_stat (
                name TEXT PRIMARY KEY,
                value_num REAL,
                value_text TEXT,
                updated_at TEXT,
                source TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS club_info (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT,
                tag TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS club_stat (
                name TEXT PRIMARY KEY,
                value_num REAL,
                value_text TEXT,
                updated_at TEXT,
                source TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS club_roster (
                platform TEXT NOT NULL,
                platform_id TEXT NOT NULL,
                display_name TEXT,
                PRIMARY KEY (platform, platform_id)
            );

            CREATE TABLE IF NOT EXISTS players (
                unique_id TEXT PRIMARY KEY,
                name TEXT,
                met_count INTEGER NOT NULL DEFAULT 0,
                first_met_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS player_playlist_records (
                unique_id TEXT NOT NULL,
                playlist_id INTEGER NOT NULL,
                relation TEXT NOT NULL CHECK (relation IN ('with', 'against')),
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT,
                PRIMARY KEY (unique_id, playlist_id, relation),
                FOREIGN KEY (unique_id) REFERENCES players(unique_id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS matches (
                match_guid TEXT PRIMARY KEY,
                playlist_id INTEGER,
                winner_team INTEGER,
                own_team INTEGER,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS match_players (
                match_guid TEXT NOT NULL,
                unique_id TEXT NOT NULL,
                name TEXT,
                team_num INTEGER,
                PRIMARY KEY (match_guid, unique_id),
                FOREIGN KEY (match_guid) REFERENCES matches(match_guid) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS shot_speeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                speed_kph REAL NOT NULL,
                match_guid TEXT,
                source_event TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        db.commit()

    def get_meta(self, key: str) -> str | None:
        row = self._db().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._db().execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._db().commit()

    def import_snapshots(self) -> None:
        self.import_player_snapshot()
        self.import_club_snapshot()
        self.import_club_roster()
        self.import_freeplay_goal_snapshot()
        self.import_dejavu_snapshot()
        self.set_meta("snapshots_imported_at", utc_now())

    def import_player_snapshot(self) -> None:
        path = self.data_dir / PLAYER_YAML
        if not path.exists():
            return

        data = load_yaml_like(path)
        if not isinstance(data, dict):
            return

        captured_at = _as_text(data.get("datetime"))
        profile = data.get("profile", {})
        if isinstance(profile, dict):
            self._db().execute(
                """
                INSERT INTO profile (id, platform, platform_id, display_name, captured_at)
                VALUES (1, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    platform = excluded.platform,
                    platform_id = excluded.platform_id,
                    display_name = excluded.display_name,
                    captured_at = excluded.captured_at
                """,
                (
                    _as_text(profile.get("platform")),
                    _as_text(profile.get("platformId")),
                    _as_text(profile.get("displayName")),
                    captured_at,
                ),
            )

        mmr_rows = data.get("MMR", [])
        if isinstance(mmr_rows, list):
            for row in mmr_rows:
                if not isinstance(row, dict):
                    continue
                playlist_id = _to_int(row.get("playlistId"))
                name = _as_text(row.get("name"))
                if playlist_id is None or not name:
                    continue
                self._db().execute(
                    """
                    INSERT INTO playlist_mmr (playlist_id, name, value, updated_at, source)
                    VALUES (?, ?, ?, ?, 'player.yml')
                    ON CONFLICT(playlist_id) DO UPDATE SET
                        name = excluded.name,
                        value = excluded.value,
                        updated_at = excluded.updated_at,
                        source = excluded.source
                    """,
                    (playlist_id, name, _to_float(row.get("value")), captured_at or utc_now()),
                )

        stats = data.get("Stats", {})
        if isinstance(stats, dict):
            for name, value in _flatten("", stats):
                self.upsert_stat("career_stat", name, value, "player.yml", prefer_larger=True)

        career_record = data.get("Career Record", {})
        if isinstance(career_record, dict):
            for name, value in _flatten("Career Record", career_record):
                self.upsert_stat("career_stat", name, value, "player.yml", prefer_larger=True)

        self._db().commit()

    def import_club_snapshot(self) -> None:
        path = self.data_dir / CLUB_YAML
        if not path.exists():
            return

        data = load_yaml_like(path)
        if not isinstance(data, dict):
            return

        updated_at = _as_text(data.get("datetime")) or utc_now()
        self._db().execute(
            """
            INSERT INTO club_info (id, name, tag, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                tag = excluded.tag,
                updated_at = excluded.updated_at
            """,
            (_as_text(data.get("Club Name")), _as_text(data.get("Club Tag")), updated_at),
        )

        for section_name in ("Club Stats", "Club Record"):
            section = data.get(section_name, {})
            if isinstance(section, dict):
                prefix = "" if section_name == "Club Stats" else section_name
                for name, value in _flatten(prefix, section):
                    self.upsert_stat("club_stat", name, value, "club.yml", prefer_larger=True)

        self._db().commit()

    def import_club_roster(self) -> None:
        path = self.data_dir / CLUB_ROSTER_YAML
        if not path.exists():
            return

        data = load_yaml_like(path)
        if not isinstance(data, dict):
            return

        roster = data.get("roster", [])
        if not isinstance(roster, list):
            return

        for member in roster:
            if not isinstance(member, dict):
                continue
            platform = _as_text(member.get("platform"))
            platform_id = _as_text(member.get("platformId"))
            if not platform or not platform_id:
                continue
            self._db().execute(
                """
                INSERT INTO club_roster (platform, platform_id, display_name)
                VALUES (?, ?, ?)
                ON CONFLICT(platform, platform_id) DO UPDATE SET
                    display_name = excluded.display_name
                """,
                (platform, platform_id, _as_text(member.get("displayName"))),
            )

        self._db().commit()

    def import_freeplay_goal_snapshot(self) -> None:
        path = self.data_dir / FREEPLAY_GOAL_YAML
        if not path.exists():
            return

        data = load_yaml_like(path)
        if not isinstance(data, dict):
            return

        speed = _to_float(data.get("goalSpeed"))
        if speed is None:
            return

        created_at = _as_text(data.get("timestamp")) or utc_now()
        existing = self._db().execute(
            """
            SELECT 1 FROM shot_speeds
            WHERE source_event = 'snapshot:freeplay_goal.yml' AND created_at = ? AND speed_kph = ?
            """,
            (created_at, speed),
        ).fetchone()
        if existing:
            return

        self._db().execute(
            """
            INSERT INTO shot_speeds (speed_kph, match_guid, source_event, created_at)
            VALUES (?, NULL, 'snapshot:freeplay_goal.yml', ?)
            """,
            (speed, created_at),
        )
        self._db().commit()

    def import_dejavu_snapshot(self) -> None:
        yml_path = self.data_dir / DEJAVU_YAML
        legacy_yml_path = self.data_dir / LEGACY_DEJAVU_YAML
        json_path = self.data_dir / DEJAVU_JSON_BACKUP

        source_yml_path = yml_path if yml_path.exists() else legacy_yml_path
        if source_yml_path.exists():
            data = load_yaml_like(source_yml_path)
            players = data.get("players", []) if isinstance(data, dict) else []
            if isinstance(players, list):
                self._import_dejavu_yaml_players(players)
                return

        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8-sig"))
            players = data.get("players", {}) if isinstance(data, dict) else {}
            if isinstance(players, dict):
                self._import_dejavu_json_players(players)

    def _import_dejavu_yaml_players(self, players: list[Any]) -> None:
        rows_seen = 0
        for player in players:
            if not isinstance(player, dict):
                continue
            unique_id = _as_text(player.get("uniqueId"))
            if not unique_id:
                continue

            self.import_player(
                unique_id=unique_id,
                name=_as_text(player.get("name")),
                met_count=_to_int(player.get("metCount")) or 0,
                first_met_at=_as_text(player.get("timeMet")),
                updated_at=_as_text(player.get("updatedAt")),
            )

            playlists = player.get("playlists", [])
            if isinstance(playlists, list):
                for playlist in playlists:
                    if not isinstance(playlist, dict):
                        continue
                    playlist_id = _to_int(playlist.get("playlistId"))
                    records = playlist.get("records", {})
                    if playlist_id is None or not isinstance(records, dict):
                        continue
                    for relation in ("with", "against"):
                        record = records.get(relation)
                        if not isinstance(record, dict):
                            continue
                        self.import_player_record(
                            unique_id=unique_id,
                            playlist_id=playlist_id,
                            relation=relation,
                            wins=_to_int(record.get("wins")) or 0,
                            losses=_to_int(record.get("losses")) or 0,
                        )
            rows_seen += 1
            if rows_seen % 1000 == 0:
                self._db().commit()

        self._db().commit()

    def _import_dejavu_json_players(self, players: dict[str, Any]) -> None:
        rows_seen = 0
        for unique_id, player in players.items():
            if not isinstance(player, dict):
                continue
            self.import_player(
                unique_id=str(unique_id),
                name=_as_text(player.get("name")),
                met_count=_to_int(player.get("metCount")) or 0,
                first_met_at=_as_text(player.get("timeMet")),
                updated_at=_as_text(player.get("updatedAt")),
            )

            playlist_data = player.get("playlistData", {})
            if isinstance(playlist_data, dict):
                for playlist_id_text, playlist in playlist_data.items():
                    playlist_id = _to_int(playlist_id_text)
                    records = playlist.get("records", {}) if isinstance(playlist, dict) else {}
                    if playlist_id is None or not isinstance(records, dict):
                        continue
                    for relation in ("with", "against"):
                        record = records.get(relation)
                        if not isinstance(record, dict):
                            continue
                        self.import_player_record(
                            unique_id=str(unique_id),
                            playlist_id=playlist_id,
                            relation=relation,
                            wins=_to_int(record.get("wins")) or 0,
                            losses=_to_int(record.get("losses")) or 0,
                        )
            rows_seen += 1
            if rows_seen % 1000 == 0:
                self._db().commit()

        self._db().commit()

    def upsert_stat(
        self,
        table: str,
        name: str,
        value: Any,
        source: str,
        prefer_larger: bool = False,
    ) -> None:
        if table not in {"career_stat", "club_stat"}:
            raise ValueError(f"Unsupported stat table: {table}")

        value_num = _to_float(value)
        value_text = None if value_num is not None else _as_text(value)
        existing = self._db().execute(f"SELECT value_num, value_text FROM {table} WHERE name = ?", (name,)).fetchone()

        if existing and prefer_larger and value_num is not None and existing["value_num"] is not None:
            if float(existing["value_num"]) > value_num:
                return

        self._db().execute(
            f"""
            INSERT INTO {table} (name, value_num, value_text, updated_at, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                value_num = excluded.value_num,
                value_text = excluded.value_text,
                updated_at = excluded.updated_at,
                source = excluded.source
            """,
            (name, value_num, value_text, utc_now(), source),
        )

    def get_profile(self) -> sqlite3.Row | None:
        return self._db().execute("SELECT * FROM profile WHERE id = 1").fetchone()

    def get_self_tokens(self) -> set[str]:
        profile = self.get_profile()
        tokens: set[str] = set()
        if not profile:
            return tokens
        for key in ("platform_id", "display_name"):
            value = profile[key]
            if value:
                tokens.add(str(value).strip().lower())
        return tokens

    def get_playlist_mmr(self, playlist_id: int | None) -> sqlite3.Row | None:
        if playlist_id is None:
            return None
        return self._db().execute("SELECT * FROM playlist_mmr WHERE playlist_id = ?", (playlist_id,)).fetchone()

    def get_stat_value(self, table: str, name: str) -> float | str | None:
        if table not in {"career_stat", "club_stat"}:
            raise ValueError(f"Unsupported stat table: {table}")
        row = self._db().execute(f"SELECT value_num, value_text FROM {table} WHERE name = ?", (name,)).fetchone()
        if not row:
            return None
        return row["value_num"] if row["value_num"] is not None else row["value_text"]

    def increment_career_stats(self, deltas: dict[str, int | float]) -> None:
        for name, delta in deltas.items():
            if not delta:
                continue
            current = self.get_stat_value("career_stat", name)
            current_num = _to_float(current) or 0.0
            self.upsert_stat("career_stat", name, current_num + float(delta), "statsapi")
        self._db().commit()

    def import_player(
        self,
        unique_id: str,
        name: str | None,
        met_count: int,
        first_met_at: str | None,
        updated_at: str | None,
    ) -> None:
        self._db().execute(
            """
            INSERT INTO players (unique_id, name, met_count, first_met_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(unique_id) DO UPDATE SET
                name = COALESCE(excluded.name, players.name),
                met_count = MAX(players.met_count, excluded.met_count),
                first_met_at = COALESCE(players.first_met_at, excluded.first_met_at),
                updated_at = COALESCE(excluded.updated_at, players.updated_at)
            """,
            (unique_id, name, met_count, first_met_at, updated_at),
        )

    def import_player_record(self, unique_id: str, playlist_id: int, relation: str, wins: int, losses: int) -> None:
        if relation not in {"with", "against"}:
            return
        self._db().execute(
            """
            INSERT INTO player_playlist_records (unique_id, playlist_id, relation, wins, losses, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(unique_id, playlist_id, relation) DO UPDATE SET
                wins = MAX(player_playlist_records.wins, excluded.wins),
                losses = MAX(player_playlist_records.losses, excluded.losses),
                updated_at = excluded.updated_at
            """,
            (unique_id, playlist_id, relation, wins, losses, utc_now()),
        )

    def increment_player_record(
        self,
        unique_id: str,
        name: str | None,
        playlist_id: int,
        relation: str,
        won: bool,
        timestamp: str,
    ) -> None:
        if relation not in {"with", "against"}:
            return

        self._db().execute(
            """
            INSERT INTO players (unique_id, name, met_count, first_met_at, updated_at)
            VALUES (?, ?, 1, ?, ?)
            ON CONFLICT(unique_id) DO UPDATE SET
                name = COALESCE(excluded.name, players.name),
                met_count = players.met_count + 1,
                updated_at = excluded.updated_at
            """,
            (unique_id, name, timestamp, timestamp),
        )
        self._db().execute(
            """
            INSERT INTO player_playlist_records (unique_id, playlist_id, relation, wins, losses, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(unique_id, playlist_id, relation) DO UPDATE SET
                wins = player_playlist_records.wins + excluded.wins,
                losses = player_playlist_records.losses + excluded.losses,
                updated_at = excluded.updated_at
            """,
            (unique_id, playlist_id, relation, 1 if won else 0, 0 if won else 1, timestamp),
        )

    def match_exists(self, match_guid: str) -> bool:
        row = self._db().execute("SELECT 1 FROM matches WHERE match_guid = ?", (match_guid,)).fetchone()
        return row is not None

    def record_completed_match(
        self,
        match_guid: str,
        playlist_id: int | None,
        winner_team: int | None,
        own_team: int | None,
        players: list["ObservedPlayer"],
        timestamp: str,
    ) -> bool:
        if self.match_exists(match_guid):
            return False

        self._db().execute(
            """
            INSERT INTO matches (match_guid, playlist_id, winner_team, own_team, completed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (match_guid, playlist_id, winner_team, own_team, timestamp),
        )

        for player in players:
            if not player.unique_id:
                continue
            self._db().execute(
                """
                INSERT INTO match_players (match_guid, unique_id, name, team_num)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(match_guid, unique_id) DO UPDATE SET
                    name = excluded.name,
                    team_num = excluded.team_num
                """,
                (match_guid, player.unique_id, player.name, player.team_num),
            )

        self._db().commit()
        return True

    def record_shot_speed(self, speed_kph: float, match_guid: str | None, source_event: str, created_at: str) -> None:
        self._db().execute(
            """
            INSERT INTO shot_speeds (speed_kph, match_guid, source_event, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (speed_kph, match_guid, source_event, created_at),
        )
        self._db().commit()

    def get_last_shot_speed(self) -> float | None:
        row = self._db().execute("SELECT speed_kph FROM shot_speeds ORDER BY id DESC LIMIT 1").fetchone()
        return float(row["speed_kph"]) if row else None

    def get_best_shot_speed(self) -> float | None:
        row = self._db().execute("SELECT MAX(speed_kph) AS speed FROM shot_speeds").fetchone()
        return float(row["speed"]) if row and row["speed"] is not None else None

    def get_last_10_avg_shot_speed(self) -> float | None:
        rows = self._db().execute("SELECT speed_kph FROM shot_speeds ORDER BY id DESC LIMIT 10").fetchall()
        if not rows:
            return None
        return sum(float(row["speed_kph"]) for row in rows) / len(rows)

    def get_club_display(self) -> str:
        row = self._db().execute("SELECT name, tag FROM club_info WHERE id = 1").fetchone()
        if not row:
            return ""
        name = row["name"] or ""
        tag = row["tag"] or ""
        return f"[{tag}] {name}" if tag else name

    def get_dejavu_record(self, unique_id: str, playlist_id: int, relation: str) -> sqlite3.Row | None:
        return self._db().execute(
            """
            SELECT p.met_count, r.wins, r.losses
            FROM players p
            LEFT JOIN player_playlist_records r
                ON r.unique_id = p.unique_id AND r.playlist_id = ? AND r.relation = ?
            WHERE p.unique_id = ?
            """,
            (playlist_id, relation, unique_id),
        ).fetchone()


@dataclass
class ObservedPlayer:
    unique_id: str | None
    name: str | None
    team_num: int | None
    stats: dict[str, Any] = field(default_factory=dict)
    demolished: bool = False


@dataclass
class CurrentMatch:
    play_mode: str = "menu"
    match_guid: str | None = None
    playlist_id: int | None = None
    own_team: int | None = None
    winner_team: int | None = None
    clock: str = "0:00"
    overtime: bool = False
    event_name: str = "Waiting"
    event_banner: str = ""
    players: dict[str, ObservedPlayer] = field(default_factory=dict)
    stat_values: dict[str, int] = field(default_factory=dict)
    team_scores: dict[int, int] = field(default_factory=dict)
    started: bool = False
    self_demolished: bool = False
    counted_without_guid: bool = False
    recent_update_ball_speeds: list[dict[str, float | None]] = field(default_factory=list)
    last_update_ball_speed_kph: float | None = None
    last_freeplay_goal_message_index: int | None = None
    last_freeplay_goal_elapsed: float | None = None
    last_freeplay_goal_frame: float | None = None
    last_freeplay_goal_had_speed: bool = False


class OverlayStatsTracker:
    DEACTIVATE_AFTER_EVENTS = {"MatchEnded", "PodiumStart"}
    STAT_FIELDS = {
        "goals": ("gameGoals", "GameGoals", "game_goals", "Goals", "goals"),
        "assists": ("gameAssists", "GameAssists", "game_assists", "Assists", "assists"),
        "saves": ("gameSaves", "GameSaves", "game_saves", "Saves", "saves"),
        "shots": ("gameShots", "GameShots", "game_shots", "Shots", "shots"),
        "low_fives": ("gameLowFives", "GameLowFives", "game_low_fives", "LowFives", "lowFives", "low_fives"),
        "high_fives": (
            "gameHighFives",
            "GameHighFives",
            "game_high_fives",
            "HighFives",
            "highFives",
            "high_fives",
        ),
        "demos": ("gameDemolitions", "GameDemolitions", "gameDemos", "GameDemos", "Demos", "Demolitions", "demos"),
        "deaths": ("gameDeaths", "GameDeaths", "Deaths", "deaths", "TimesDemolished", "timesDemolished"),
    }
    CAREER_NAMES = {
        "goals": "Goals",
        "assists": "Assists",
        "saves": "Saves",
        "shots": "Shots",
        "low_fives": "Low Fives",
        "high_fives": "High Fives",
        "demos": "Demolitions",
        "deaths": "Deaths",
    }
    SPEED_FIELDS = (
        "goalSpeed",
        "GoalSpeed",
        "shotSpeed",
        "ShotSpeed",
        "ballSpeed",
        "BallSpeed",
        "PostHitSpeed",
        "speed",
        "Speed",
    )
    STARTED_EVENTS = {
        "BallHit",
        "ClockUpdatedSeconds",
        "CrossbarHit",
        "GoalReplayEnd",
        "GoalReplayStart",
        "GoalReplayWillEnd",
        "GoalScored",
        "RoundStarted",
        "StatfeedEvent",
    }
    PLAYER_ACTIVITY_FIELDS = (
        "Score",
        "score",
        "Touches",
        "touches",
        "CarTouches",
        "carTouches",
        "car_touches",
    )

    def __init__(self, store: StatsStore, obs_dir: Path | None = None):
        self.store = store
        self.obs_dir = obs_dir
        self.current = CurrentMatch()
        self.self_tokens = store.get_self_tokens()
        self.session_wins = 0
        self.session_losses = 0
        self.streak_kind: str | None = None
        self.streak_count = 0
        self.session_counts = dict.fromkeys(self.STAT_FIELDS, 0)
        self.session_shots: list[float] = []
        self.last_goal_speed_kph: float | None = None
        self.file_cache: dict[Path, str] = {}
        self.inactive_match_guids: set[str] = set()
        self.message_index = 0
        self.self_tokens.update(KNOWN_SELF_TOKENS)

        if self.obs_dir is not None:
            self.obs_dir.mkdir(parents=True, exist_ok=True)
            self.write_overlay_files()

    def handle_message(self, message: dict[str, Any]) -> None:
        self.message_index += 1
        event = str(message.get("Event", "Unknown"))
        data = parse_data_field(message)
        self.current.event_name = event
        self._update_live_display(event, data)

        match_guid = _find_first_key(data, ("MatchGuid", "MatchGUID", "MatchId", "MatchID"))
        match_guid_text = self._normalize_match_guid(match_guid)
        if event in {"MatchCreated", "MatchInitialized"} and match_guid_text:
            self.inactive_match_guids.discard(match_guid_text)
        players = _extract_players(data)
        play_mode = self._infer_play_mode(event, match_guid_text, players)
        if self._should_reset_current(event, play_mode, match_guid_text):
            self.current = CurrentMatch(
                play_mode=play_mode,
                match_guid=match_guid_text if play_mode == "match" else None,
                clock=self.current.clock,
                overtime=self.current.overtime,
                event_name=self.current.event_name,
                event_banner=(
                    self.current.event_banner if play_mode != "menu" and event in {"GoalScored", "MatchEnded"} else ""
                ),
            )

        playlist_id = _extract_playlist_id(data)
        if playlist_id is not None:
            self.current.playlist_id = playlist_id

        self._track_update_state_ball_speed(event, data)

        teams = _extract_teams(data)
        if teams:
            self._maybe_record_freeplay_score_goal(event, data, teams)
            self.current.team_scores.update(teams)

        if players:
            if self.current.play_mode in {"match", "freeplay"}:
                for player in players:
                    player_key = player.unique_id or player.name
                    if player_key:
                        self.current.players[player_key] = player
                    if self._is_self(player) and player.team_num is not None:
                        self.current.own_team = player.team_num

                self._update_current_player_stats(players)

        self._update_started_state(event, data, players, teams)
        self._maybe_record_freeplay_shot(event, data)

        if event == "MatchEnded":
            self._handle_match_ended(data)
        if event in self.DEACTIVATE_AFTER_EVENTS or event == "MatchDestroyed":
            if match_guid_text:
                self.inactive_match_guids.add(match_guid_text)
            self.current.play_mode = "menu"

        self.write_overlay_files()

    def _infer_play_mode(self, event: str, match_guid: str | None, players: list[ObservedPlayer]) -> str:
        if event == "MatchDestroyed":
            return "menu"
        if match_guid and match_guid in self.inactive_match_guids:
            return "menu"
        if match_guid:
            return "match"
        if event in {"MatchCreated", "MatchInitialized"}:
            return "match"
        if event == "UpdateState":
            return "freeplay" if len(players) == 1 else "menu"
        return self.current.play_mode

    def _should_reset_current(self, event: str, play_mode: str, match_guid: str | None) -> bool:
        if play_mode != self.current.play_mode:
            return True
        if play_mode == "match":
            return bool(match_guid and match_guid != self.current.match_guid)
        return event in {"UpdateState", "MatchDestroyed"} and self.current.match_guid is not None

    @staticmethod
    def _normalize_match_guid(value: Any) -> str | None:
        text = _as_text(value)
        if text is None:
            return None
        text = text.strip()
        return text or None

    def _update_live_display(self, event: str, data: dict[str, Any]) -> None:
        time_seconds = _extract_time_seconds(data)
        if time_seconds is not None:
            self.current.overtime = _extract_bool(data, ("bOvertime", "Overtime", "overtime")) or False
            self.current.clock = self._format_clock(time_seconds, self.current.overtime)

        if event == "GoalScored":
            scorer = data.get("Scorer", {})
            scorer_name = "Unknown"
            if isinstance(scorer, dict):
                scorer_name = _as_text(_first_value(scorer, ("Name", "PlayerName", "DisplayName", "name"))) or "Unknown"
            self.current.event_banner = f"GOAL: {scorer_name}"
        elif event == "MatchEnded":
            winner_team = _to_int(data.get("WinnerTeamNum"))
            if winner_team == 0:
                self.current.event_banner = "MATCH ENDED - BLUE WIN"
            elif winner_team == 1:
                self.current.event_banner = "MATCH ENDED - ORANGE WIN"
            else:
                self.current.event_banner = "MATCH ENDED"

    def _is_self(self, player: ObservedPlayer) -> bool:
        candidates = _identity_tokens(player.unique_id, player.name)
        return any(candidate and candidate in self.self_tokens for candidate in candidates)

    def _is_self_mapping(self, value: dict[str, Any]) -> bool:
        candidates = _identity_tokens(_extract_player_id(value), _extract_player_name(value))
        return any(candidate and candidate in self.self_tokens for candidate in candidates)

    def _update_current_player_stats(self, players: list[ObservedPlayer]) -> None:
        self_player = next((player for player in players if self._is_self(player)), None)
        if self_player is None:
            return

        for stat_key, field_names in self.STAT_FIELDS.items():
            if stat_key == "deaths":
                continue
            value = _get_number_from_fields(self_player.stats, field_names)
            if value is None:
                continue
            stat_value = max(0, int(value))
            if stat_key == "goals" and self.current.play_mode == "freeplay":
                stat_value = max(self.current.stat_values.get("goals", 0), stat_value)
            self.current.stat_values[stat_key] = stat_value

        if self_player.demolished and not self.current.self_demolished:
            self.current.stat_values["deaths"] = self.current.stat_values.get("deaths", 0) + 1
        self.current.self_demolished = self_player.demolished

    def _update_started_state(
        self,
        event: str,
        data: dict[str, Any],
        players: list[ObservedPlayer],
        teams: dict[int, int],
    ) -> None:
        if self.current.play_mode != "match" or self.current.started:
            return
        if event in self.STARTED_EVENTS:
            self.current.started = True
            return
        if any(score > 0 for score in teams.values()):
            self.current.started = True
            return
        if self._players_have_match_activity(players):
            self.current.started = True
            return
        if self._ball_has_match_activity(data):
            self.current.started = True
            return
        if _extract_bool(data, ("bOvertime", "Overtime", "overtime")):
            self.current.started = True

    def _players_have_match_activity(self, players: list[ObservedPlayer]) -> bool:
        for player in players:
            player_activity = _get_number_from_fields(player.stats, self.PLAYER_ACTIVITY_FIELDS) or 0
            if player_activity > 0:
                return True
            for field_names in self.STAT_FIELDS.values():
                if (_get_number_from_fields(player.stats, field_names) or 0) > 0:
                    return True
        return False

    @staticmethod
    def _ball_has_match_activity(data: dict[str, Any]) -> bool:
        ball = _find_first_key(data, ("Ball", "ball"))
        if not isinstance(ball, dict):
            return False
        team_num = _to_int(
            _first_value(
                ball,
                ("TeamNum", "teamNum", "LastTouchTeamNum", "lastTouchTeamNum"),
            )
        )
        if team_num in {0, 1}:
            return True
        return (
            _get_number_from_fields(
                ball,
                ("PostHitSpeed", "postHitSpeed", "BallSpeed", "ballSpeed"),
            )
            or 0
        ) > 0

    def _handle_match_ended(self, data: dict[str, Any]) -> None:
        winner_team = _to_int(data.get("WinnerTeamNum"))
        if winner_team not in {0, 1}:
            winner_team = None
        self.current.winner_team = winner_team

        if self.current.own_team is None or winner_team is None:
            return
        if not self.current.started:
            return

        match_guid = self.current.match_guid
        if match_guid and self.store.match_exists(match_guid):
            return
        if not match_guid and self.current.counted_without_guid:
            return

        timestamp = utc_now()
        players = list(self.current.players.values())
        if match_guid:
            recorded = self.store.record_completed_match(
                match_guid=match_guid,
                playlist_id=self.current.playlist_id,
                winner_team=winner_team,
                own_team=self.current.own_team,
                players=players,
                timestamp=timestamp,
            )
        else:
            recorded = True
            self.current.counted_without_guid = True

        if not recorded:
            return

        won = winner_team == self.current.own_team
        if won:
            self.session_wins += 1
            self._update_streak("W")
        else:
            self.session_losses += 1
            self._update_streak("L")

        career_increments = {
            "Wins" if won else "Losses": 1,
            "Career Record.Total Matches Played": 1,
        }
        for stat_key, value in self.current.stat_values.items():
            if value <= 0:
                continue
            self.session_counts[stat_key] += value
            career_name = self.CAREER_NAMES.get(stat_key)
            if career_name:
                career_increments[career_name] = career_increments.get(career_name, 0) + value
        self.store.increment_career_stats(career_increments)

        if self.current.playlist_id is not None:
            for player in players:
                if not player.unique_id or self._is_self(player) or player.team_num is None:
                    continue
                relation = "with" if player.team_num == self.current.own_team else "against"
                self.store.increment_player_record(
                    unique_id=player.unique_id,
                    name=player.name,
                    playlist_id=self.current.playlist_id,
                    relation=relation,
                    won=won,
                    timestamp=timestamp,
                )
            self.store._db().commit()

    def _update_streak(self, kind: str) -> None:
        if self.streak_kind == kind:
            self.streak_count += 1
        else:
            self.streak_kind = kind
            self.streak_count = 1

    def _maybe_record_freeplay_shot(self, event: str, data: dict[str, Any]) -> None:
        event_lower = event.lower()
        event_token = re.sub(r"[^a-z0-9]", "", event_lower)
        result = _normalize_token(_find_first_key(data, ("result", "Result", "ShotResult")))
        mode = _normalize_token(_find_first_key(data, ("mode", "Mode", "GameMode")))
        is_goal = event_token.endswith("goalscored") or event_token == "freeplaygoal" or result == "goal"
        is_freeplay = "freeplay" in event_lower or mode == "freeplay" or self.current.play_mode == "freeplay"

        if not is_goal:
            return
        if not self._is_self_goal(data, is_freeplay):
            return

        speed = _extract_speed_kph(data, self.SPEED_FIELDS)
        if not is_freeplay:
            if speed is not None:
                self.last_goal_speed_kph = speed
            return

        count = 1 if self.current.play_mode == "freeplay" else 0
        self._record_freeplay_goal(event, data, speed, count=count)

    def _track_update_state_ball_speed(self, event: str, data: dict[str, Any]) -> None:
        if event != "UpdateState":
            return

        speed = _extract_ball_speed_kph(data, self.SPEED_FIELDS)
        if speed is None:
            return

        self.current.last_update_ball_speed_kph = speed
        if speed <= 0:
            return

        elapsed, frame = _extract_update_timing(data)
        recent = self.current.recent_update_ball_speeds
        recent.append({"speed": speed, "elapsed": elapsed, "frame": frame})
        _prune_recent_update_ball_speeds(recent, elapsed, frame)

    def _maybe_record_freeplay_score_goal(self, event: str, data: dict[str, Any], scores: dict[int, int]) -> None:
        if event != "UpdateState" or self.current.play_mode != "freeplay":
            return

        previous_scores = self.current.team_scores
        if not previous_scores:
            return

        if _scores_decreased(previous_scores, scores):
            self.current.recent_update_ball_speeds = []
            return

        goal_count = _score_increment(previous_scores, scores)
        if goal_count <= 0:
            return

        elapsed, frame = _extract_update_timing(data)
        speed = _best_recent_update_ball_speed(self.current.recent_update_ball_speeds, elapsed, frame)
        if speed is None or speed <= 0:
            speed = self.current.last_update_ball_speed_kph
        if speed is not None and speed <= 0:
            speed = None

        count = 0 if self._is_recent_freeplay_goal(elapsed, frame) else goal_count
        self._record_freeplay_goal("UpdateStateScoreIncrease", data, speed, count=count)

    def _record_freeplay_goal(
        self,
        event: str,
        data: dict[str, Any],
        speed: float | None,
        *,
        count: int,
    ) -> None:
        if count > 0:
            self.current.stat_values["goals"] = self.current.stat_values.get("goals", 0) + count
            self.current.last_freeplay_goal_had_speed = False

        should_record_speed = speed is not None and speed > 0 and (
            count > 0 or not self.current.last_freeplay_goal_had_speed
        )
        if should_record_speed:
            self.last_goal_speed_kph = speed
            timestamp = _as_text(_find_first_key(data, ("timestamp", "Timestamp", "time", "Time"))) or utc_now()
            self.store.record_shot_speed(speed, None, event, timestamp)
            self.session_shots.append(speed)
            self.current.last_freeplay_goal_had_speed = True

        elapsed, frame = _extract_update_timing(data)
        self.current.last_freeplay_goal_message_index = self.message_index
        self.current.last_freeplay_goal_elapsed = elapsed
        self.current.last_freeplay_goal_frame = frame
        self.current.recent_update_ball_speeds = []

    def _is_recent_freeplay_goal(self, elapsed: float | None, frame: float | None) -> bool:
        last_elapsed = self.current.last_freeplay_goal_elapsed
        if elapsed is not None and last_elapsed is not None:
            delta = elapsed - last_elapsed
            return 0 <= delta <= FREEPLAY_GOAL_DEDUPE_SECONDS

        last_frame = self.current.last_freeplay_goal_frame
        if frame is not None and last_frame is not None:
            delta = frame - last_frame
            return 0 <= delta <= FREEPLAY_GOAL_DEDUPE_FRAMES

        last_message = self.current.last_freeplay_goal_message_index
        if last_message is None:
            return False
        return 0 <= self.message_index - last_message <= FREEPLAY_GOAL_DEDUPE_MESSAGES

    def _is_self_goal(self, data: dict[str, Any], is_freeplay: bool) -> bool:
        scorer = data.get("Scorer") or data.get("scorer")
        if isinstance(scorer, dict):
            return self._is_self_mapping(scorer)
        if is_freeplay:
            return True
        return False

    def write_overlay_files(self) -> None:
        if self.obs_dir is None:
            return

        outputs = {
            "clock.txt": self.current.clock,
            "score_blue.txt": str(self.current.team_scores.get(0, 0)),
            "score_orange.txt": str(self.current.team_scores.get(1, 0)),
            "event_name.txt": self.current.event_name,
            "event_banner.txt": self.current.event_banner,
            "session_wins.txt": str(self.session_wins),
            "session_losses.txt": str(self.session_losses),
            "session_streak.txt": self._format_streak(),
            "session_low_fives.txt": str(self.session_counts["low_fives"]),
            "session_high_fives.txt": str(self.session_counts["high_fives"]),
            "session_demos.txt": str(self.session_counts["demos"]),
            "session_deaths.txt": str(self.session_counts["deaths"]),
            "recent_mmr.txt": self._format_recent_mmr(),
            "lifetime_low_fives.txt": self._format_number(self.store.get_stat_value("career_stat", "Low Fives")),
            "lifetime_high_fives.txt": self._format_number(self.store.get_stat_value("career_stat", "High Fives")),
            "lifetime_demos.txt": self._format_number(self.store.get_stat_value("career_stat", "Demolitions")),
            "lifetime_deaths.txt": self._format_number(self.store.get_stat_value("career_stat", "Deaths")),
            "last_goal_speed.txt": self._format_speed(self.last_goal_speed_kph),
            "freeplay_last_shot.txt": self._format_speed(self.store.get_last_shot_speed()),
            "freeplay_session_best.txt": self._format_speed(max(self.session_shots) if self.session_shots else None),
            "freeplay_all_time_best.txt": self._format_speed(self.store.get_best_shot_speed()),
            "freeplay_avg_last_10.txt": self._format_speed(self.store.get_last_10_avg_shot_speed()),
            "club_name.txt": self.store.get_club_display(),
            "club_record.txt": self._format_club_record(),
            "dejavu_players.txt": self._format_dejavu_players(),
        }

        for filename, value in outputs.items():
            self._write_text_if_changed(self.obs_dir / filename, value)
        self._write_text_if_changed(
            self.obs_dir / "overlay_state.json",
            json.dumps(self.get_overlay_state(), ensure_ascii=True, sort_keys=True, indent=2),
        )

    def _write_text_if_changed(self, path: Path, value: str) -> None:
        if self.file_cache.get(path) == value:
            return
        path.write_text(value, encoding="utf-8")
        self.file_cache[path] = value

    def get_overlay_state(self) -> dict[str, Any]:
        active = self.current.play_mode in {"match", "freeplay"}
        return {
            "context": {
                "mode": self.current.play_mode,
                "active": active,
                "freeplay": self.current.play_mode == "freeplay",
            },
            "clock": self.current.clock,
            "overtime": self.current.overtime,
            "scores": {
                "blue": self.current.team_scores.get(0, 0),
                "orange": self.current.team_scores.get(1, 0),
            },
            "event": {
                "name": self.current.event_name,
                "banner": self.current.event_banner,
            },
            "match": {
                "active": active,
                "mode": self.current.play_mode,
                "guid": self.current.match_guid,
                "playlist_id": self.current.playlist_id,
                "own_team": self.current.own_team,
                "winner_team": self.current.winner_team,
                "last_goal_speed": self._format_speed(self.last_goal_speed_kph),
                "stats": {stat_key: self.current.stat_values.get(stat_key, 0) for stat_key in self.STAT_FIELDS},
            },
            "session": {
                "wins": self.session_wins,
                "losses": self.session_losses,
                "streak": self._format_streak(),
                **self.session_counts,
            },
            "career": {
                "goals": self._format_number(self.store.get_stat_value("career_stat", "Goals")),
                "assists": self._format_number(self.store.get_stat_value("career_stat", "Assists")),
                "saves": self._format_number(self.store.get_stat_value("career_stat", "Saves")),
                "shots": self._format_number(self.store.get_stat_value("career_stat", "Shots")),
                "deaths": self._format_number(self.store.get_stat_value("career_stat", "Deaths")),
                "low_fives": self._format_number(self.store.get_stat_value("career_stat", "Low Fives")),
                "high_fives": self._format_number(self.store.get_stat_value("career_stat", "High Fives")),
                "demos": self._format_number(self.store.get_stat_value("career_stat", "Demolitions")),
            },
            "freeplay": {
                "last_shot": self._format_speed(self.store.get_last_shot_speed()),
                "session_best": self._format_speed(max(self.session_shots) if self.session_shots else None),
                "all_time_best": self._format_speed(self.store.get_best_shot_speed()),
                "avg_last_10": self._format_speed(self.store.get_last_10_avg_shot_speed()),
            },
            "club": {
                "name": self.store.get_club_display(),
                "record": self._format_club_record(),
            },
            "mmr": {
                "recent": self._format_recent_mmr(),
            },
            "dejavu": self._get_dejavu_players(),
        }

    def _format_streak(self) -> str:
        if not self.streak_kind or self.streak_count == 0:
            return "0"
        return f"{self.streak_kind}{self.streak_count}"

    def _format_recent_mmr(self) -> str:
        row = self.store.get_playlist_mmr(self.current.playlist_id)
        if not row:
            return "MMR pending"
        value = row["value"]
        value_text = "--" if value is None else self._format_number(value)
        return f"{row['name']}: {value_text}"

    def _format_club_record(self) -> str:
        matches = self.store.get_stat_value("club_stat", "Club Record.Matches Played")
        ratio = self.store.get_stat_value("club_stat", "Club Record.Win Ratio")
        wins = self.store.get_stat_value("club_stat", "Wins")
        parts = []
        if wins is not None:
            parts.append(f"{self._format_number(wins)} W")
        if matches is not None:
            parts.append(f"{self._format_number(matches)} matches")
        if ratio is not None:
            parts.append(f"{self._format_number(ratio)}%")
        return " / ".join(parts)

    def _format_dejavu_players(self) -> str:
        lines = [player["display"] for player in self._get_dejavu_players()]
        return "\n".join(lines[:6])

    def _get_dejavu_players(self) -> list[dict[str, Any]]:
        if self.current.playlist_id is None or self.current.own_team is None:
            return []

        players = []
        for player in self.current.players.values():
            if self._is_self(player) or not player.unique_id or player.team_num is None:
                continue
            relation = "with" if player.team_num == self.current.own_team else "against"
            row = self.store.get_dejavu_record(player.unique_id, self.current.playlist_id, relation)
            if not row or row["met_count"] is None:
                continue
            wins = row["wins"] or 0
            losses = row["losses"] or 0
            met_count = row["met_count"] or 0
            if met_count == 0 and wins == 0 and losses == 0:
                continue
            prefix = "with" if relation == "with" else "vs"
            display = f"{player.name or player.unique_id}: {prefix} {wins}-{losses} ({met_count})"
            players.append(
                {
                    "name": player.name or player.unique_id,
                    "relation": relation,
                    "wins": wins,
                    "losses": losses,
                    "met_count": met_count,
                    "display": display,
                }
            )

        return players[:6]

    @staticmethod
    def _format_clock(time_seconds: int, overtime: bool) -> str:
        minutes = max(0, time_seconds) // 60
        seconds = max(0, time_seconds) % 60
        clock = f"{minutes}:{seconds:02d}"
        if overtime:
            return f"OT {clock}"
        return clock

    @staticmethod
    def _format_number(value: Any) -> str:
        number = _to_float(value)
        if number is None:
            return "" if value is None else str(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.1f}"

    @classmethod
    def _format_speed(cls, speed: float | None) -> str:
        if speed is None:
            return "-- kph"
        return f"{cls._format_number(speed)} kph"


def _normalize_token(value: Any) -> str | None:
    text = _as_text(value)
    if text is None:
        return None
    text = text.strip().lower()
    return text or None


def _identity_tokens(*values: Any) -> set[str]:
    tokens = set()
    for value in values:
        token = _normalize_token(value)
        if not token:
            continue
        tokens.add(token)
        tokens.update(part for part in re.split(r"[|:/\\]", token) if part)
    return tokens


def _first_value(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    return None


def _find_first_key(value: Any, keys: tuple[str, ...], depth: int = 0) -> Any:
    if depth > 5:
        return None
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                return value[key]
        for child in value.values():
            found = _find_first_key(child, keys, depth + 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first_key(child, keys, depth + 1)
            if found is not None:
                return found
    return None


def _extract_playlist_id(data: dict[str, Any]) -> int | None:
    value = _find_first_key(data, ("PlaylistId", "PlaylistID", "PlaylistNum", "playlistId", "playlist_id"))
    playlist_id = _to_int(value)
    if playlist_id is not None:
        return playlist_id

    playlist = _find_first_key(data, ("Playlist", "playlist"))
    if isinstance(playlist, dict):
        return _to_int(_first_value(playlist, ("Id", "ID", "PlaylistId", "playlistId")))
    return _to_int(playlist)


def _extract_teams(data: dict[str, Any]) -> dict[int, int]:
    teams_value = None
    game = data.get("Game")
    if isinstance(game, dict):
        teams_value = game.get("Teams")
    if teams_value is None:
        teams_value = data.get("Teams")

    scores: dict[int, int] = {}
    if not isinstance(teams_value, list):
        return scores

    for team in teams_value:
        if not isinstance(team, dict):
            continue
        team_num = _to_int(_first_value(team, ("TeamNum", "Team", "TeamIndex", "teamNum")))
        score = _to_int(_first_value(team, ("Score", "score")))
        if team_num is not None and score is not None:
            scores[team_num] = score
    return scores


def _extract_time_seconds(data: dict[str, Any]) -> int | None:
    value = _find_first_key(data, ("TimeSeconds", "SecondsRemaining", "timeSeconds", "secondsRemaining"))
    return _to_int(value)


def _extract_bool(data: dict[str, Any], keys: tuple[str, ...]) -> bool | None:
    value = _find_first_key(data, keys)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y"}:
            return True
        if lowered in {"false", "0", "no", "n"}:
            return False
    return None


def _extract_players(data: dict[str, Any]) -> list[ObservedPlayer]:
    raw_players: list[tuple[dict[str, Any], int | None]] = []

    for container in (data, data.get("Game")):
        if not isinstance(container, dict):
            continue
        players = _first_value(container, ("Players", "players"))
        if isinstance(players, list):
            raw_players.extend((player, None) for player in players if isinstance(player, dict))

        teams = _first_value(container, ("Teams", "teams"))
        if isinstance(teams, list):
            for team in teams:
                if not isinstance(team, dict):
                    continue
                team_num = _to_int(_first_value(team, ("TeamNum", "Team", "TeamIndex", "teamNum")))
                team_players = _first_value(team, ("Players", "players"))
                if isinstance(team_players, list):
                    raw_players.extend((player, team_num) for player in team_players if isinstance(player, dict))

    single_player = data.get("Player")
    if isinstance(single_player, dict):
        raw_players.append((single_player, None))

    players: list[ObservedPlayer] = []
    seen: set[str] = set()
    for raw, fallback_team in raw_players:
        unique_id = _extract_player_id(raw)
        name = _extract_player_name(raw)
        team_num = _extract_player_team(raw, fallback_team)
        key = unique_id or name or json.dumps(raw, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        stats = dict(raw)
        nested_stats = raw.get("Stats") or raw.get("stats")
        if isinstance(nested_stats, dict):
            stats.update(nested_stats)
        players.append(
            ObservedPlayer(
                unique_id=unique_id,
                name=name,
                team_num=team_num,
                stats=stats,
                demolished=_extract_player_demolished(stats),
            )
        )

    return players


def _extract_player_id(player: dict[str, Any]) -> str | None:
    for key in (
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
        "SteamID",
        "EpicAccountId",
        "PlayerID",
    ):
        value = _as_text(player.get(key))
        if value:
            return value

    platform = player.get("Platform")
    if isinstance(platform, dict):
        return _as_text(_first_value(platform, ("PlatformId", "Id", "ID", "OnlineID")))
    return None


def _extract_player_name(player: dict[str, Any]) -> str | None:
    for key in ("Name", "PlayerName", "DisplayName", "displayName", "name"):
        value = _as_text(player.get(key))
        if value:
            return value
    return None


def _extract_player_team(player: dict[str, Any], fallback: int | None) -> int | None:
    team = _to_int(_first_value(player, ("TeamNum", "Team", "TeamIndex", "team", "teamNum")))
    if team is not None:
        return team
    return fallback


def _extract_player_demolished(player: dict[str, Any]) -> bool:
    return _extract_bool(
        player,
        ("bDemolished", "Demolished", "demolished", "isDemolished", "IsDemolished", "bIsDemolished"),
    ) or False


def _get_number_from_fields(stats: dict[str, Any], field_names: tuple[str, ...]) -> float | None:
    for field_name in field_names:
        value = _to_float(stats.get(field_name))
        if value is not None:
            return value
    return None


def _extract_ball_speed_kph(data: dict[str, Any], field_names: tuple[str, ...]) -> float | None:
    ball = _find_first_key(data, ("Ball", "ball"))
    if not isinstance(ball, dict):
        return None

    speed = _get_number_from_fields(ball, field_names)
    if speed is None:
        return None

    unit = _normalize_token(_find_first_key(ball, ("unit", "Unit", "speedUnit", "SpeedUnit")))
    if unit is None:
        unit = _normalize_token(_find_first_key(data, ("unit", "Unit", "speedUnit", "SpeedUnit")))
    if unit in {"mph", "mi/h"}:
        return speed * 1.609344
    return speed


def _extract_update_timing(data: dict[str, Any]) -> tuple[float | None, float | None]:
    elapsed = _to_float(_find_first_key(data, ("Elapsed", "elapsed")))
    frame = _to_float(_find_first_key(data, ("Frame", "frame")))
    return elapsed, frame


def _prune_recent_update_ball_speeds(
    recent: list[dict[str, float | None]],
    elapsed: float | None,
    frame: float | None,
) -> None:
    if elapsed is not None:
        cutoff = elapsed - FREEPLAY_SPEED_WINDOW_SECONDS
        recent[:] = [sample for sample in recent if sample.get("elapsed") is None or sample["elapsed"] >= cutoff]
        return

    if frame is not None:
        cutoff = frame - FREEPLAY_SPEED_WINDOW_FRAMES
        recent[:] = [sample for sample in recent if sample.get("frame") is None or sample["frame"] >= cutoff]


def _best_recent_update_ball_speed(
    recent: list[dict[str, float | None]],
    elapsed: float | None,
    frame: float | None,
) -> float | None:
    if elapsed is not None or frame is not None:
        _prune_recent_update_ball_speeds(recent, elapsed, frame)

    speeds = [_to_float(sample.get("speed")) for sample in recent if isinstance(sample, dict)]
    speeds = [speed for speed in speeds if speed is not None]
    return max(speeds) if speeds else None


def _score_increment(previous_scores: dict[int, int], scores: dict[int, int]) -> int:
    increment = 0
    for team_num, score in scores.items():
        previous = previous_scores.get(team_num)
        if previous is not None and score > previous:
            increment += score - previous
    return increment


def _scores_decreased(previous_scores: dict[int, int], scores: dict[int, int]) -> bool:
    for team_num, score in scores.items():
        previous = previous_scores.get(team_num)
        if previous is not None and score < previous:
            return True
    return False


def _extract_speed_kph(data: dict[str, Any], field_names: tuple[str, ...]) -> float | None:
    speed = None
    for field_name in field_names:
        speed = _to_float(_find_first_key(data, (field_name,)))
        if speed is not None:
            break
    if speed is None:
        return None

    unit = _normalize_token(_find_first_key(data, ("unit", "Unit", "speedUnit", "SpeedUnit"))) or "kph"
    if unit in {"mph", "mi/h"}:
        return speed * 1.609344
    return speed
