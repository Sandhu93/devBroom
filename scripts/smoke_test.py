from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [command, *args],
        capture_output=True,
        check=False,
        text=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the installed DevBroom CLI using disposable folders.")
    parser.add_argument(
        "--keep-fixture",
        action="store_true",
        help="Keep the generated project after the dry-run so it can be reviewed in the GUI.",
    )
    args = parser.parse_args()

    command = shutil.which("devbroom")
    if command is None:
        parser.error("devbroom is not installed or not on PATH; run: python -m pip install -e .")

    fixture_root = Path(tempfile.mkdtemp(prefix="devbroom-smoke-")).resolve()
    preserve_fixture = args.keep_fixture
    project_root = fixture_root / "sample-project"
    node_modules = project_root / "node_modules"
    venv_root = project_root / ".venv"

    try:
        (project_root / ".git").mkdir(parents=True)
        node_modules.mkdir()
        (node_modules / "package.json").write_text("{}", encoding="utf-8")
        (venv_root / "Scripts").mkdir(parents=True)
        (venv_root / "pyvenv.cfg").write_text("home = smoke-test\n", encoding="utf-8")

        scan = run_command(
            command,
            "--cli",
            "--path",
            str(fixture_root),
            "--dry-run",
            "--no-settings-ignores",
        )
        scan_text = scan.stdout + scan.stderr
        if scan.returncode != 0:
            raise RuntimeError(f"Dry-run failed with exit code {scan.returncode}:\n{scan_text}")
        if "node_modules" not in scan_text or ".venv" not in scan_text or "DRY RUN" not in scan_text:
            raise RuntimeError(f"Dry-run did not report both expected targets:\n{scan_text}")
        if not node_modules.is_dir() or not venv_root.is_dir():
            raise RuntimeError("Dry-run removed or changed a fixture target.")

        print("PASS: dry-run found node_modules and .venv and left both in place.")

        if args.keep_fixture:
            print(f"Fixture kept for GUI review: {fixture_root}")
            print("Open DevBroom, scan this path, cancel the delete dialog once, then confirm if you want to test GUI deletion.")
            return 0

        deletion = run_command(
            command,
            "--cli",
            "--path",
            str(fixture_root),
            "--delete",
            "--yes",
            "--no-settings-ignores",
        )
        deletion_text = deletion.stdout + deletion.stderr
        if deletion.returncode != 0:
            raise RuntimeError(f"Fixture deletion failed with exit code {deletion.returncode}:\n{deletion_text}")
        if node_modules.exists() or venv_root.exists():
            raise RuntimeError(f"CLI returned success but did not remove both fixture targets:\n{deletion_text}")

        print("PASS: CLI deleted only the generated smoke-test targets.")
        return 0
    finally:
        if not preserve_fixture:
            shutil.rmtree(fixture_root)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
