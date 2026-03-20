from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import re

from devbroom import __version__
from devbroom.app import build_parser, run_cli
from devbroom.cli import format_targets_table, write_json_report, write_text_report
from devbroom.models import NODE_MODULES_NAME, ScanTarget, VENV_KIND
from devbroom.settings import AppSettings


TEST_ROOT = Path(__file__).resolve().parent / ".tmp"


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        TEST_ROOT.mkdir(exist_ok=True)
        self.workdir = TEST_ROOT / uuid.uuid4().hex
        self.workdir.mkdir()

    def tearDown(self) -> None:
        shutil.rmtree(self.workdir, ignore_errors=True)

    def test_format_targets_table_handles_empty_results(self) -> None:
        self.assertEqual(format_targets_table([]), "No cleanup targets found.")

    def test_write_json_report_writes_expected_payload(self) -> None:
        targets = [
            ScanTarget(path=Path("/tmp/project/node_modules"), kind=NODE_MODULES_NAME, size=1024),
            ScanTarget(path=Path("/tmp/project/.venv"), kind=VENV_KIND, size=2048),
        ]
        output = self.workdir / "report.json"

        write_json_report(targets, output)

        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["total_size_bytes"], 3072)
        self.assertEqual(len(payload["targets"]), 2)

    def test_write_text_report_writes_table_output(self) -> None:
        targets = [ScanTarget(path=Path("/tmp/project/node_modules"), kind=NODE_MODULES_NAME, size=1024)]
        output = self.workdir / "report.txt"

        write_text_report(targets, output)

        text = output.read_text(encoding="utf-8")
        self.assertIn("TYPE", text)
        self.assertIn("node_modules", text)
        self.assertIn("Found 1 folders totaling 1.0 KB.", text)

    def test_run_cli_scans_and_prints_results(self) -> None:
        node_modules = self.workdir / "app" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(self.workdir, None, use_settings_ignores=False)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("node_modules", output)
        self.assertIn("Total reclaimable size:", output)

    def test_run_cli_returns_error_for_invalid_path(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(self.workdir / "missing", None, use_settings_ignores=False)

        self.assertEqual(exit_code, 1)
        self.assertIn("Not a directory:", buffer.getvalue())

    def test_run_cli_uses_saved_ignored_paths_when_enabled(self) -> None:
        ignored_root = self.workdir / "ignored"
        ignored_target = ignored_root / NODE_MODULES_NAME
        ignored_target.mkdir(parents=True)
        (ignored_target / "package.json").write_text("{}", encoding="ascii")

        kept_target = self.workdir / "kept" / NODE_MODULES_NAME
        kept_target.mkdir(parents=True)
        (kept_target / "package.json").write_text("{}", encoding="ascii")

        settings = AppSettings(last_path=str(self.workdir), theme="dark", ignored_paths=(str(ignored_root),))
        buffer = io.StringIO()
        with patch("devbroom.app.load_settings", return_value=settings):
            with redirect_stdout(buffer):
                exit_code = run_cli(self.workdir, None, use_settings_ignores=True)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(str(kept_target), output)
        self.assertNotIn(str(ignored_target), output)
        self.assertIn("Using 1 ignored path(s).", output)

    def test_run_cli_can_ignore_saved_ignored_paths(self) -> None:
        ignored_root = self.workdir / "ignored"
        ignored_target = ignored_root / NODE_MODULES_NAME
        ignored_target.mkdir(parents=True)
        (ignored_target / "package.json").write_text("{}", encoding="ascii")

        settings = AppSettings(last_path=str(self.workdir), theme="dark", ignored_paths=(str(ignored_root),))
        buffer = io.StringIO()
        with patch("devbroom.app.load_settings", return_value=settings):
            with redirect_stdout(buffer):
                exit_code = run_cli(self.workdir, None, use_settings_ignores=False)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn(str(ignored_target), output)
        self.assertNotIn("Using 1 ignored path(s).", output)

    def test_version_is_non_empty_semver_string(self) -> None:
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")

    def test_version_flag_prints_version_and_exits(self) -> None:
        parser = build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_build_parser_parses_cli_arguments(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--cli", "--path", "demo", "--json-out", "out.json", "--no-settings-ignores"])

        self.assertTrue(args.cli)
        self.assertEqual(args.path, Path("demo"))
        self.assertEqual(args.json_out, Path("out.json"))
        self.assertTrue(args.no_settings_ignores)

    def test_build_parser_parses_delete_flags(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--cli", "--path", "demo", "--delete", "--yes"])

        self.assertTrue(args.delete)
        self.assertTrue(args.yes)
        self.assertFalse(args.dry_run)

    def test_build_parser_parses_dry_run_flag(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["--cli", "--path", "demo", "--dry-run"])

        self.assertTrue(args.dry_run)
        self.assertFalse(args.delete)

    def test_dry_run_prints_banner_and_does_not_delete(self) -> None:
        node_modules = self.workdir / "app" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(self.workdir, None, use_settings_ignores=False, dry_run=True)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("DRY RUN", output)
        self.assertTrue(node_modules.exists(), "--dry-run must not delete anything")

    def test_delete_with_yes_removes_targets(self) -> None:
        node_modules = self.workdir / "app" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(self.workdir, None, use_settings_ignores=False, delete=True, yes=True)

        output = buffer.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertFalse(node_modules.exists(), "node_modules should have been deleted")
        self.assertIn("Deleted", output)

    def test_delete_and_dry_run_are_mutually_exclusive(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(self.workdir, None, use_settings_ignores=False, delete=True, dry_run=True)

        self.assertEqual(exit_code, 1)
        self.assertIn("mutually exclusive", buffer.getvalue())

    def test_delete_writes_json_report(self) -> None:
        node_modules = self.workdir / "app" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")
        report_path = self.workdir / "deleted.json"

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run_cli(
                self.workdir, report_path, use_settings_ignores=False, delete=True, yes=True
            )

        self.assertEqual(exit_code, 0)
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["deleted_count"], 1)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(len(payload["deleted"]), 1)

    def test_delete_aborts_on_no_confirmation(self) -> None:
        node_modules = self.workdir / "app" / "node_modules"
        node_modules.mkdir(parents=True)
        (node_modules / "package.json").write_text("{}", encoding="ascii")

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            with patch("builtins.input", return_value="n"):
                exit_code = run_cli(self.workdir, None, use_settings_ignores=False, delete=True, yes=False)

        self.assertEqual(exit_code, 0)
        self.assertTrue(node_modules.exists(), "node_modules should NOT be deleted when user says no")
        self.assertIn("Aborted", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
