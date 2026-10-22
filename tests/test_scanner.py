from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.models import NODE_MODULES_NAME, ScanDiagnostics, VENV_KIND
from devbroom.scanner import (
    human_age,
    human_size,
    is_inside_git_repo,
    is_virtualenv,
    iter_scan_targets,
    safe_folder_size,
    safe_folder_stats,
)


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

    def test_is_virtualenv_detects_activation_script_marker(self) -> None:
        venv_path = self.workdir / "venv"
        activate = venv_path / "bin" / "activate"
        activate.parent.mkdir(parents=True)
        activate.write_text("", encoding="ascii")
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

    def test_iter_scan_targets_skips_real_virtualenv_named_env(self) -> None:
        env_path = self.workdir / "project" / "env"
        env_path.mkdir(parents=True)
        (env_path / "pyvenv.cfg").write_text("", encoding="ascii")

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

    def test_iter_scan_targets_skips_symlinked_target(self) -> None:
        external_target = self.workdir / "external"
        external_target.mkdir()
        (external_target / "package.json").write_text("{}", encoding="ascii")
        project = self.workdir / "project"
        project.mkdir()
        link = project / NODE_MODULES_NAME
        try:
            os.symlink(external_target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable in this environment")

        targets = list(iter_scan_targets(self.workdir, threading.Event()))

        self.assertEqual(targets, [])
        self.assertTrue((external_target / "package.json").exists())

    def test_iter_scan_targets_skips_reparse_point_candidate(self) -> None:
        target = self.workdir / "project" / NODE_MODULES_NAME
        target.mkdir(parents=True)
        (target / "package.json").write_text("{}", encoding="ascii")

        with patch(
            "devbroom.scanner.is_link_or_junction",
            side_effect=lambda path, on_error=None: path == target,
        ):
            targets = list(iter_scan_targets(self.workdir, threading.Event()))

        self.assertEqual(targets, [])

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
        original_safe_folder_stats = safe_folder_stats

        def stop_after_first(
            path: Path,
            event: threading.Event | None = None,
            diagnostics: ScanDiagnostics | None = None,
        ) -> tuple[int, float | None]:
            stats = original_safe_folder_stats(path, event, diagnostics)
            stop_event.set()
            return stats

        with patch("devbroom.scanner.safe_folder_stats", side_effect=stop_after_first):
            targets = list(iter_scan_targets(self.workdir, stop_event))

        self.assertEqual(len(targets), 1)
        self.assertIn(targets[0].path, {first_target, second_target})
        self.assertTrue(stop_event.is_set())

    def test_iter_scan_targets_skips_target_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            node_modules = tmp_path / "app" / "node_modules"
            node_modules.mkdir(parents=True)
            (node_modules / "package.json").write_text("{}", encoding="ascii")

            targets = list(iter_scan_targets(tmp_path, threading.Event()))

            self.assertEqual(targets, [], "node_modules outside a git repo should be skipped by default")

    def test_iter_scan_targets_include_non_project_finds_target_outside_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            node_modules = tmp_path / "app" / "node_modules"
            node_modules.mkdir(parents=True)
            (node_modules / "package.json").write_text("{}", encoding="ascii")

            targets = list(iter_scan_targets(tmp_path, threading.Event(), require_git_repo=False))

            self.assertEqual(len(targets), 1)
            self.assertEqual(targets[0].path, node_modules)

    def test_is_inside_git_repo_returns_true_for_project_subpath(self) -> None:
        # self.workdir lives under the project repo, so this must be True
        self.assertTrue(is_inside_git_repo(self.workdir))

    def test_is_inside_git_repo_returns_false_outside_any_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self.assertFalse(is_inside_git_repo(Path(tmpdir)))

    def test_scan_target_has_non_negative_age_days(self) -> None:
        node_modules = self.workdir / "app" / NODE_MODULES_NAME
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        targets = list(iter_scan_targets(self.workdir, threading.Event()))

        self.assertEqual(len(targets), 1)
        self.assertGreaterEqual(targets[0].age_days, 0.0)

    def test_iter_scan_targets_older_than_excludes_fresh_target(self) -> None:
        node_modules = self.workdir / "app" / NODE_MODULES_NAME
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        # older_than=3650 (10 years) — a freshly created folder should be filtered out
        targets = list(iter_scan_targets(self.workdir, threading.Event(), older_than=3650))

        self.assertEqual(targets, [], "A freshly created folder should not appear with older_than=3650")

    def test_age_uses_newest_nested_file_modification(self) -> None:
        target = self.workdir / "app" / NODE_MODULES_NAME
        nested = target / "package" / "lib"
        nested.mkdir(parents=True)
        old_time = 1_600_000_000
        changed_file = nested / "recent.js"
        changed_file.write_text("recent", encoding="ascii")
        recent_time = 1_700_000_000
        os.utime(changed_file, (recent_time, recent_time))
        os.utime(nested, (old_time, old_time))
        os.utime(target / "package", (old_time, old_time))
        os.utime(target, (old_time, old_time))

        _size, age_days = safe_folder_stats(target)

        expected_days = max(0.0, (time.time() - recent_time) / 86400)
        self.assertAlmostEqual(age_days, expected_days, delta=0.01)

    def test_partial_target_keeps_unknown_age_and_is_not_filtered_by_age(self) -> None:
        app = self.workdir / "app"
        target = app / NODE_MODULES_NAME
        target.mkdir(parents=True)
        (target / "package.json").write_text("{}", encoding="ascii")
        diagnostics = ScanDiagnostics()

        def walk_with_permission_error(path, topdown=True, onerror=None, followlinks=False):
            del topdown, followlinks
            current = Path(path)
            if current == self.workdir:
                yield str(current), ["app"], []
                yield str(app), [NODE_MODULES_NAME], []
                yield str(target), [], []
            else:
                error = PermissionError(13, "permission denied", str(target / "locked.bin"))
                if onerror:
                    onerror(error)
                yield str(target), [], ["package.json"]

        with patch("devbroom.scanner.os.walk", side_effect=walk_with_permission_error):
            results = list(
                iter_scan_targets(
                    self.workdir,
                    threading.Event(),
                    older_than=90,
                    diagnostics=diagnostics,
                )
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].path, target)
        self.assertFalse(results[0].size_complete)
        self.assertIsNone(results[0].age_days)
        self.assertTrue(diagnostics.incomplete)
        self.assertIn("locked.bin", diagnostics.errors[0])

    def test_iter_scan_targets_reports_unreadable_scan_subtree(self) -> None:
        diagnostics = ScanDiagnostics()

        def walk_with_unreadable_subtree(path, topdown=True, onerror=None, followlinks=False):
            del topdown, followlinks
            error = PermissionError(13, "permission denied", str(Path(path) / "restricted"))
            if onerror:
                onerror(error)
            yield str(path), [], []

        with patch("devbroom.scanner.os.walk", side_effect=walk_with_unreadable_subtree):
            results = list(
                iter_scan_targets(self.workdir, threading.Event(), diagnostics=diagnostics)
            )

        self.assertEqual(results, [])
        self.assertTrue(diagnostics.incomplete)
        self.assertIn("restricted", diagnostics.errors[0])

    def test_iter_scan_targets_older_than_zero_shows_all(self) -> None:
        node_modules = self.workdir / "app" / NODE_MODULES_NAME
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        targets = list(iter_scan_targets(self.workdir, threading.Event(), older_than=0))

        self.assertEqual(len(targets), 1)

    def test_human_age_formats_days(self) -> None:
        self.assertEqual(human_age(None), "Unknown")
        self.assertEqual(human_age(0.5), "< 1d")
        self.assertEqual(human_age(14), "14d")
        self.assertEqual(human_age(45), "1mo")
        self.assertEqual(human_age(365), "1.0yr")

    def test_safe_folder_size_honors_stop_event(self) -> None:
        target = self.workdir / "project" / NODE_MODULES_NAME
        nested = target / "nested"
        nested.mkdir(parents=True)
        (target / "a.bin").write_bytes(b"a" * 32)
        (nested / "b.bin").write_bytes(b"b" * 32)

        stop_event = threading.Event()

        def stop_during_walk(
            path: Path,
            topdown: bool = True,
            onerror=None,
            followlinks: bool = False,
        ):
            del topdown, onerror, followlinks
            yield str(path), ["nested"], ["a.bin"]
            stop_event.set()
            yield str(nested), [], ["b.bin"]

        with patch("devbroom.scanner.os.walk", side_effect=stop_during_walk):
            total = safe_folder_size(target, stop_event)

        self.assertEqual(total, 32)

    def test_safe_folder_stats_skips_symlinked_files(self) -> None:
        target = self.workdir / "node_modules"
        target.mkdir()
        source = self.workdir / "large.bin"
        source.write_bytes(b"x" * 128)
        try:
            (target / "linked.bin").symlink_to(source)
        except (OSError, NotImplementedError):
            self.skipTest("file symlinks unavailable in this environment")
        (target / "real.bin").write_bytes(b"y" * 8)

        size, _age_days = safe_folder_stats(target)

        self.assertEqual(size, 8)


if __name__ == "__main__":
    unittest.main()
