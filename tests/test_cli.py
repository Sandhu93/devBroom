from __future__ import annotations

import io
import json
import shutil
import sys
import unittest
import uuid
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from devbroom.app import run_cli
from devbroom.cli import format_targets_table, write_json_report, write_text_report
from devbroom.models import NODE_MODULES_NAME, ScanTarget, VENV_KIND


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


if __name__ == "__main__":
    unittest.main()
