from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .cli import delete_targets, format_targets_table, scan_targets, write_json_report
from .models import ScanDiagnostics
from .scanner import human_size
from .settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DevBroom: clean development dependency folders.")
    parser.add_argument("--version", "-V", action="version", version=f"devBroom {__version__}")
    parser.add_argument("--cli", action="store_true", help="Run in headless CLI mode.")
    parser.add_argument("--path", type=Path, help="Root directory to scan.")
    parser.add_argument("--json-out", type=Path, help="Write scan results to a JSON file.")
    parser.add_argument("--no-settings-ignores", action="store_true", help="Ignore saved ignore paths.")
    parser.add_argument("--delete", action="store_true", help="Delete all discovered targets after scanning.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without removing anything.")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt when deleting.")
    parser.add_argument("--include-non-project", action="store_true", help="Include targets not inside a git repository (e.g. installed apps).")
    parser.add_argument(
        "--older-than",
        type=int,
        metavar="N",
        help="Only show targets with no filesystem changes in the last N days.",
    )
    return parser


def run_gui() -> int:
    try:
        from .ui import DevBroomApp
    except ImportError:
        print("Error: the GUI requires tkinter, which is not available on this system.")
        print("")
        print("  Install tkinter:")
        print("    Debian/Ubuntu:  sudo apt install python3-tk")
        print("    Fedora:         sudo dnf install python3-tkinter")
        print("    Termux:         pkg install python-tkinter")
        print("")
        print("  Or use CLI mode instead:")
        print("    devbroom --cli --path /path/to/your/projects")
        return 1

    app = DevBroomApp(settings=load_settings())
    app.mainloop()
    return 0


def run_cli(
    root: Path | None,
    json_out: Path | None,
    use_settings_ignores: bool,
    delete: bool = False,
    dry_run: bool = False,
    yes: bool = False,
    include_non_project: bool = False,
    older_than: int | None = None,
) -> int:
    if delete and dry_run:
        print("Error: --delete and --dry-run are mutually exclusive.")
        return 1

    settings = load_settings()
    scan_root = (root or Path(settings.last_path or Path.home())).expanduser()
    if not scan_root.is_dir():
        print(f"Not a directory: {scan_root}")
        return 1

    ignored_paths = () if not use_settings_ignores else settings.ignored_paths
    diagnostics = ScanDiagnostics()
    targets = sorted(
        scan_targets(
            scan_root,
            ignored_paths=ignored_paths,
            require_git_repo=not include_non_project,
            older_than=older_than,
            show_progress=True,
            diagnostics=diagnostics,
        ),
        key=lambda t: t.size,
        reverse=True,
    )
    print(format_targets_table(targets, diagnostics=diagnostics))

    if ignored_paths:
        print(f"Using {len(ignored_paths)} ignored path(s).")
    print(f"Scan root: {scan_root}")
    total_prefix = (
        "at least "
        if any(not target.size_complete for target in targets) or diagnostics.incomplete
        else ""
    )
    print(f"Total reclaimable size: {total_prefix}{human_size(sum(target.size for target in targets))}")
    if any(not target.size_complete for target in targets):
        print("WARNING: Some target sizes are lower bounds; inaccessible contents may be omitted.")
    if diagnostics.incomplete:
        print(
            f"WARNING: Scan incomplete; encountered {diagnostics.error_count} filesystem error(s). "
            "Results and estimates may be incomplete."
        )
        for error in diagnostics.errors:
            print(f"  {error}")
        if diagnostics.error_count > len(diagnostics.errors):
            print(f"  ... and {diagnostics.error_count - len(diagnostics.errors)} more error(s).")

    if dry_run:
        print("\nDRY RUN — nothing deleted.")
        return 0

    if delete and targets:
        return delete_targets(targets, json_out=json_out, yes=yes, diagnostics=diagnostics)

    if json_out:
        write_json_report(targets, json_out, diagnostics=diagnostics)
        print(f"JSON report written to {json_out}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cli:
        return run_cli(
            args.path,
            args.json_out,
            use_settings_ignores=not args.no_settings_ignores,
            delete=args.delete,
            dry_run=args.dry_run,
            yes=args.yes,
            include_non_project=args.include_non_project,
            older_than=args.older_than,
        )

    return run_gui()
