from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.settings import AppSettings

try:
    import tkinter as tk
except ImportError:
    tk = None

if tk is not None:
    from devbroom.ui import DevBroomApp
else:
    DevBroomApp = None


class UiSmokeTests(unittest.TestCase):
    def test_main_window_builds_and_closes(self) -> None:
        if tk is None or DevBroomApp is None:
            self.skipTest("Tkinter is not installed")
        try:
            app = DevBroomApp(settings=AppSettings())
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")

        try:
            app.withdraw()
            app.update_idletasks()
            self.assertEqual(app.title(), "DevBroom")
            self.assertEqual(app._tree.heading(DevBroomApp.COL_AGE, "text"), "Last change")
        finally:
            app.destroy()


if __name__ == "__main__":
    unittest.main()
