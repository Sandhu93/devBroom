from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.settings import AppSettings, load_settings, save_settings


TEST_ROOT = Path(__file__).resolve().parent / ".tmp"


class SettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_ROOT.mkdir(exist_ok=True)
        self.workdir = TEST_ROOT / uuid.uuid4().hex
        self.workdir.mkdir()
        self.settings_file = self.workdir / "settings.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_load_settings_returns_defaults_when_missing(self) -> None:
        settings = load_settings(self.settings_file)
        self.assertEqual(settings, AppSettings())

    def test_save_and_load_round_trip(self) -> None:
        expected = AppSettings(last_path="D:/projects/demo", theme="light")
        save_settings(expected, self.settings_file)
        loaded = load_settings(self.settings_file)
        self.assertEqual(loaded, expected)

    def test_load_settings_falls_back_on_invalid_json(self) -> None:
        self.settings_file.write_text("{invalid", encoding="utf-8")
        settings = load_settings(self.settings_file)
        self.assertEqual(settings, AppSettings())

    def test_load_settings_normalizes_invalid_values(self) -> None:
        self.settings_file.write_text(
            json.dumps({"last_path": 123, "theme": "midnight"}),
            encoding="utf-8",
        )
        settings = load_settings(self.settings_file)
        self.assertEqual(settings, AppSettings(last_path="", theme="dark"))


if __name__ == "__main__":
    unittest.main()
