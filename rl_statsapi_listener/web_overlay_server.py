from __future__ import annotations

import argparse
import json
import math
import mimetypes
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .overlay_state import load_yaml_like


StateProvider = Callable[[], dict[str, Any]]
DEFAULT_REFERENCE_RESOLUTION = {"w": 2560, "h": 1440}
DEFAULT_SAFEZONES = {
    "match": {
        "stats": {
            "size": {"w": 422, "h": 447},
            "position": {"x": 0, "y": 802},
        }
    },
    "menu": {
        "stats": {
            "size": {"w": 1567, "h": 51},
            "position": {"x": 892, "y": 1289},
        }
    },
}


def start_web_overlay_server(
    host: str,
    port: int,
    state_provider: StateProvider,
    data_dir: Path | str | None = None,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = ThreadingHTTPServer((host, port), make_overlay_handler(state_provider, data_dir=data_dir))
    thread = threading.Thread(target=server.serve_forever, name="web-overlay-server", daemon=True)
    thread.start()
    return server, thread


def make_overlay_handler(
    state_provider: StateProvider,
    data_dir: Path | str | None = None,
) -> type[BaseHTTPRequestHandler]:
    asset_root = files("rl_statsapi_listener.web_overlay")
    source_media_root = Path(__file__).resolve().parents[1] / "media"
    media_root = source_media_root if source_media_root.exists() else Path.cwd() / "media"
    overlay_data_dir = Path(data_dir) if data_dir is not None else Path(".data")

    class OverlayHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path in {"/", "/index.html"}:
                self._serve_asset("index.html")
                return
            if path == "/state.json":
                self._serve_state()
                return
            if path == "/layout.json":
                self._serve_layout()
                return
            if path.startswith("/media/"):
                self._serve_media(path)
                return

            asset_name = PurePosixPath(path).name
            if asset_name in {"styles.css", "overlay.js"}:
                self._serve_asset(asset_name)
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def _serve_state(self) -> None:
            try:
                payload = state_provider()
            except Exception as exc:
                payload = {"error": str(exc)}
                status = HTTPStatus.INTERNAL_SERVER_ERROR
            else:
                status = HTTPStatus.OK

            body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_layout(self) -> None:
            payload = load_web_overlay_layout(overlay_data_dir)
            body = json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_media(self, path: str) -> None:
            requested = PurePosixPath(path)
            parts = [part for part in requested.parts if part not in {"", "/"}]
            if len(parts) < 2 or parts[0] != "media" or any(part == ".." for part in parts):
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            root = media_root.resolve()
            asset = (root / Path(*parts[1:])).resolve()
            try:
                asset.relative_to(root)
            except ValueError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            if not asset.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            body = asset.read_bytes()
            content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_asset(self, asset_name: str) -> None:
            asset = asset_root / asset_name
            try:
                body = asset.read_bytes()
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            content_type = mimetypes.guess_type(asset_name)[0] or "application/octet-stream"
            if asset_name.endswith(".html"):
                content_type = "text/html; charset=utf-8"
            elif asset_name.endswith(".css"):
                content_type = "text/css; charset=utf-8"
            elif asset_name.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return OverlayHandler


def load_web_overlay_layout(data_dir: Path | str | None = None) -> dict[str, Any]:
    overlay_data_dir = Path(data_dir) if data_dir is not None else Path(".data")
    warnings = []
    safezones = DEFAULT_SAFEZONES
    scoreboard_layouts: dict[str, Any] = {}

    safezones_path = overlay_data_dir / "safezones.yml"
    try:
        loaded_safezones = load_yaml_like(safezones_path)
    except FileNotFoundError:
        pass
    except Exception as exc:
        warnings.append(f"safezones.yml: {exc}")
    else:
        if isinstance(loaded_safezones, dict):
            safezones = loaded_safezones
        else:
            warnings.append("safezones.yml: expected a mapping")

    scoreboard_path = overlay_data_dir / "scoreboard-layouts.json"
    try:
        loaded_scoreboard_layouts = json.loads(scoreboard_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        pass
    except json.JSONDecodeError as exc:
        warnings.append(f"scoreboard-layouts.json: {exc}")
    else:
        if isinstance(loaded_scoreboard_layouts, dict):
            scoreboard_layouts = loaded_scoreboard_layouts
        else:
            warnings.append("scoreboard-layouts.json: expected a mapping")

    return {
        "reference_resolution": infer_safezone_reference_resolution(safezones),
        "safezones": safezones,
        "scoreboard_layouts": scoreboard_layouts,
        "warnings": warnings,
    }


def infer_safezone_reference_resolution(safezones: Any) -> dict[str, int]:
    width = float(DEFAULT_REFERENCE_RESOLUTION["w"])
    height = float(DEFAULT_REFERENCE_RESOLUTION["h"])

    for right, bottom in _iter_safezone_edges(safezones):
        width = max(width, right)
        height = max(height, bottom)

    return {"w": math.ceil(width), "h": math.ceil(height)}


def _iter_safezone_edges(value: Any):
    if isinstance(value, dict):
        position = value.get("position")
        size = value.get("size")
        if isinstance(position, dict) and isinstance(size, dict):
            x = _finite_number(position.get("x"))
            y = _finite_number(position.get("y"))
            w = _finite_number(size.get("w"))
            h = _finite_number(size.get("h"))
            if x is not None and y is not None and w is not None and h is not None:
                yield x + w, y + h

        for child in value.values():
            yield from _iter_safezone_edges(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_safezone_edges(child)


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value):
        return float(value)
    if isinstance(value, str):
        try:
            parsed = float(value.strip())
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _demo_state() -> dict[str, Any]:
    return {
        "context": {"mode": "match", "active": True, "freeplay": False},
        "clock": "3:21",
        "overtime": False,
        "scores": {"blue": 2, "orange": 1},
        "event": {"name": "UpdateState", "banner": "GOAL: You"},
        "match": {
            "guid": "demo",
            "playlist_id": 11,
            "own_team": 0,
            "winner_team": None,
            "stats": {"goals": 2, "assists": 1, "saves": 3, "shots": 5, "demos": 1, "high_fives": 0, "low_fives": 1},
        },
        "session": {
            "wins": 4,
            "losses": 2,
            "streak": "W2",
            "goals": 12,
            "assists": 7,
            "saves": 18,
            "shots": 29,
            "low_fives": 3,
            "high_fives": 1,
            "demos": 7,
        },
        "career": {"low_fives": "201", "high_fives": "33", "demos": "1180"},
        "freeplay": {
            "last_shot": "117.2 kph",
            "session_best": "129.8 kph",
            "all_time_best": "137.4 kph",
            "avg_last_10": "111.6 kph",
        },
        "club": {"name": "[PASS] We Say Great Pass", "record": "49 W / 100 matches / 49%"},
        "mmr": {"recent": "Ranked Doubles 2v2: 1155"},
        "dejavu": [
            {"display": "Old Mate: with 2-0 (2)"},
            {"display": "Opponent: vs 1-0 (1)"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Rocket League browser overlay demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), make_overlay_handler(_demo_state))
    print(f"Serving demo overlay at http://{args.host}:{args.port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nOverlay server stopped.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
