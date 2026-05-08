import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from rl_statsapi_listener.web_overlay_server import load_web_overlay_layout


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


class WebOverlayLayoutTests(unittest.TestCase):
    def test_loads_safezones_and_scoreboard_layouts_from_data_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            write(
                data_dir / "safezones.yml",
                """
                match:
                  stats:
                    size:
                      w: 422
                      h: 447
                    position:
                      x: 0
                      y: 802
                  controller:
                    size:
                      w: 200
                      h: 116
                    position:
                      x: 1180
                      y: 1324
                """,
            )
            write(
                data_dir / "scoreboard-layouts.json",
                json.dumps({"elements": {"score": {"size": {"w": 191, "h": 50}}}, "layouts": {}}),
            )

            layout = load_web_overlay_layout(data_dir)

        self.assertEqual(layout["reference_resolution"], {"w": 2560, "h": 1440})
        self.assertEqual(layout["safezones"]["match"]["stats"]["position"]["y"], 802)
        self.assertEqual(layout["safezones"]["match"]["controller"]["position"]["y"], 1324)
        self.assertEqual(layout["scoreboard_layouts"]["elements"]["score"]["size"]["w"], 191)
        self.assertEqual(layout["warnings"], [])

    def test_uses_defaults_when_layout_files_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = load_web_overlay_layout(Path(tmp))

        self.assertEqual(layout["safezones"]["match"]["stats"]["size"], {"w": 422, "h": 447})
        self.assertEqual(layout["safezones"]["match"]["stats"]["position"], {"x": 0, "y": 802})
        self.assertEqual(layout["safezones"]["menu"]["stats"]["size"], {"w": 1567, "h": 51})
        self.assertEqual(layout["safezones"]["menu"]["stats"]["position"], {"x": 892, "y": 1289})
        self.assertEqual(layout["scoreboard_layouts"], {})
        self.assertEqual(layout["warnings"], [])


if __name__ == "__main__":
    unittest.main()
