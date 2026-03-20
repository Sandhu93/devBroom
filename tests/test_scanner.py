from __future__ import annotations

import shutil
import sys
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.models import NODE_MODULES_NAME, VENV_KIND
from devbroom.scanner import human_size, is_virtualenv, iter_scan_targets, safe_folder_size


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

    def test_iter_scan_targets_respects_ignored_paths(self) -> None:
        ignored_root = self.workdir / "ignored"
        ignored_target = ignored_root / NODE_MODULES_NAME
        ignored_target.mkdir(parents=True)
        (ignored_target / "package.json").write_text("{}", encoding="ascii")

        kept_target = self.workdir / "kept" / NODE_MODULES_NAME
        kept_target.mkdir(parents=True)
        (kept_target / "package.json").write_text("{}", encoding="ascii")

        targets = list(iter_scan_targets(self.workdir, threading.Event(), ignored_paths=[str(ignored_root)]))

        self.assertEqual([target.path for target in targets], [kept_target])

    def test_iter_scan_targets_returns_nothing_when_cancelled_before_start(self) -> None:
        node_modules = self.workdir / "app" / NODE_MODULES_NAME
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        stop_event = threading.Event()
        stop_event.set()

        targets = list(iter_scan_targets(self.workdir, stop_event))

        self.assertEqual(targets, [])

    def test_iter_scan_targets_stops_after_first_match_when_cancelled_mid_scan(self) -> None:
        first_target = self.workdir / "first" / NODE_MODULES_NAME
        first_target.mkdir(parents=True)
        (first_target / "package.json").write_text("{}", encoding="ascii")

        second_target = self.workdir / "second" / NODE_MODULES_NAME
        second_target.mkdir(parents=True)
        (second_target / "package.json").write_text("{}", encoding="ascii")

        stop_event = threading.Event()
        original_safe_folder_size = safe_folder_size

        def stop_after_first(path: Path, event: threading.Event | None = None) -> int:
            size = original_safe_folder_size(path, event)
            stop_event.set()
            return size

        with patch("devbroom.scanner.safe_folder_size", side_effect=stop_after_first):
            targets = list(iter_scan_targets(self.workdir, stop_event))

        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].path, first_target)

    def test_safe_folder_size_honors_stop_event(self) -> None:
        target = self.workdir / "project" / NODE_MODULES_NAME
        nested = target / "nested"
        nested.mkdir(parents=True)
        (target / "a.bin").write_bytes(b"a" * 32)
        (nested / "b.bin").write_bytes(b"b" * 32)

        stop_event = threading.Event()

        def stop_during_walk(path: Path, topdown: bool = True, followlinks: bool = False):
            del topdown, followlinks
            yield str(path), ["nested"], ["a.bin"]
            stop_event.set()
            yield str(nested), [], ["b.bin"]

        with patch("devbroom.scanner.os.walk", side_effect=stop_during_walk):
            total = safe_folder_size(target, stop_event)

        self.assertEqual(total, 32)


if __name__ == "__main__":
    unittest.main()
