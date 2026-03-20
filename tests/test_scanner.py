from __future__ import annotations

import shutil
import sys
import threading
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.models import NODE_MODULES_NAME, VENV_KIND
from devbroom.scanner import human_size, is_virtualenv, iter_scan_targets


TEST_ROOT = Path(__file__).resolve().parent / ".tmp"


class RepoTempDirTestCase(unittest.TestCase):
    def setUp(self) -> None:
        TEST_ROOT.mkdir(exist_ok=True)
        self.workdir = TEST_ROOT / uuid.uuid4().hex
        self.workdir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)


class ScannerTests(RepoTempDirTestCase):
    def test_human_size_formats_bytes(self) -> None:
        self.assertEqual(human_size(0), "0.0 B")
        self.assertEqual(human_size(1024), "1.0 KB")

    def test_is_virtualenv_detects_pyvenv_cfg(self) -> None:
        venv_path = self.workdir / ".venv"
        venv_path.mkdir()
        (venv_path / "pyvenv.cfg").write_text("", encoding="ascii")
        self.assertTrue(is_virtualenv(venv_path))

    def test_iter_scan_targets_finds_node_modules_and_venv(self) -> None:
        node_modules = self.workdir / "frontend" / NODE_MODULES_NAME
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        venv_path = self.workdir / "backend" / ".venv"
        venv_path.mkdir(parents=True)
        (venv_path / "pyvenv.cfg").write_text("", encoding="ascii")

        targets = list(iter_scan_targets(self.workdir, threading.Event()))
        kinds = {target.kind for target in targets}
        paths = {target.path for target in targets}

        self.assertEqual(kinds, {NODE_MODULES_NAME, VENV_KIND})
        self.assertIn(node_modules, paths)
        self.assertIn(venv_path, paths)

    def test_iter_scan_targets_skips_fake_env_folder(self) -> None:
        fake_env = self.workdir / "project" / "env"
        fake_env.mkdir(parents=True)
        targets = list(iter_scan_targets(self.workdir, threading.Event()))
        self.assertEqual(targets, [])

    def test_iter_scan_targets_skips_nested_env_in_node_modules(self) -> None:
        nested = self.workdir / "project" / NODE_MODULES_NAME / "pkg" / ".venv"
        nested.mkdir(parents=True)
        (nested / "pyvenv.cfg").write_text("", encoding="ascii")

        targets = list(iter_scan_targets(self.workdir, threading.Event()))

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].kind, NODE_MODULES_NAME)


if __name__ == "__main__":
    unittest.main()
