from __future__ import annotations

import argparse
import json
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
DEFAULT_REFERENCE_RESOLUTION = {"w": 2560, "h": 1140}
DEFAULT_SAFEZONES = {
    "match": {
        "stats": {
            "size": {"w": 422, "h": 447},
            "position": {"x": 0, "y": 802},
        }
    }
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
        "reference_resolution": DEFAULT_REFERENCE_RESOLUTION,
        "safezones": safezones,
        "scoreboard_layouts": scoreboard_layouts,
        "warnings": warnings,
    }


def _demo_state() -> dict[str, Any]:
    return {
        "clock": "3:21",
        "overtime": False,
        "scores": {"blue": 2, "orange": 1},
        "event": {"name": "UpdateState", "banner": "GOAL: You"},
        "match": {"guid": "demo", "playlist_id": 11, "own_team": 0, "winner_team": None},
        "session": {"wins": 4, "losses": 2, "streak": "W2", "low_fives": 3, "high_fives": 1, "demos": 7},
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
