from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .cleanup import delete_tree
from .models import ScanDiagnostics, ScanTarget
from .scanner import human_age, human_size, iter_scan_targets


def scan_targets(
    root: Path,
    ignored_paths: tuple[str, ...] = (),
    require_git_repo: bool = True,
    older_than: int | None = None,
    show_progress: bool = False,
    diagnostics: ScanDiagnostics | None = None,
) -> list[ScanTarget]:
    stop_event = threading.Event()
    stats: dict = {"visited": 0}
    diagnostics = diagnostics if diagnostics is not None else ScanDiagnostics()

    if show_progress:
        _done = threading.Event()

        def _spinner() -> None:
            chars = ["|", "/", "-", "\\"]
            i = 0
            while not _done.is_set():
                print(
                    f"\r  {chars[i % 4]}  Scanning ... {stats['visited']} dirs visited",
                    end="",
                    flush=True,
                )
                i += 1
                time.sleep(0.1)

        t = threading.Thread(target=_spinner, daemon=True)
        t.start()

    results = list(
        iter_scan_targets(
            root,
            stop_event,
            ignored_paths=ignored_paths,
            require_git_repo=require_git_repo,
            older_than=older_than,
            stats=stats,
            diagnostics=diagnostics,
        )
    )

    if show_progress:
        _done.set()
        t.join()
        label = "1 target" if len(results) == 1 else f"{len(results)} targets"
        print(f"\r  Scan complete — {label} found.                        ")

    return results


def serialize_targets(targets: list[ScanTarget]) -> list[dict[str, str | int | float | bool | None]]:
    return [
        {
            "path": str(target.path),
            "kind": target.kind,
            "size_bytes": target.size,
            "size_human": human_size(target.size),
            "size_complete": target.size_complete,
            "age_days": round(target.age_days, 1) if target.age_days is not None else None,
        }
        for target in targets
    ]


def format_targets_table(
    targets: list[ScanTarget], diagnostics: ScanDiagnostics | None = None
) -> str:
    if not targets:
        return "No cleanup targets found."

    rows = [
        ("TYPE", "SIZE", "LAST CHANGE", "PATH"),
        *[
            (
                target.kind,
                ("" if target.size_complete else ">= ") + human_size(target.size),
                human_age(target.age_days),
                str(target.path),
            )
            for target in targets
        ],
    ]

    type_width = max(len(row[0]) for row in rows)
    size_width = max(len(row[1]) for row in rows)
    age_width = max(len(row[2]) for row in rows)

    lines = []
    for index, row in enumerate(rows):
        lines.append(f"{row[0]:<{type_width}}  {row[1]:>{size_width}}  {row[2]:>{age_width}}  {row[3]}")
        if index == 0:
            lines.append(f"{'-' * type_width}  {'-' * size_width}  {'-' * age_width}  {'-' * 4}")

    total_size = sum(target.size for target in targets)
    lines.append("")
    total_label = (
        "at least "
        if any(not target.size_complete for target in targets)
        or (diagnostics is not None and diagnostics.incomplete)
        else ""
    )
    lines.append(f"Found {len(targets)} folders totaling {total_label}{human_size(total_size)}.")
    return "\n".join(lines)


def write_text_report(
    targets: list[ScanTarget],
    output_path: Path,
    diagnostics: ScanDiagnostics | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = format_targets_table(targets, diagnostics=diagnostics)
    if diagnostics is not None and diagnostics.incomplete:
        warning = (
            f"WARNING: Scan incomplete; encountered {diagnostics.error_count} filesystem error(s). "
            "Results and estimates may be incomplete."
        )
        error_lines = list(diagnostics.errors)
        if diagnostics.error_count > len(error_lines):
            error_lines.append(f"... and {diagnostics.error_count - len(error_lines)} more error(s).")
        report = warning + "\n" + "\n".join(error_lines) + "\n\n" + report
    output_path.write_text(report + "\n", encoding="utf-8")


def delete_targets(
    targets: list[ScanTarget],
    json_out: Path | None = None,
    yes: bool = False,
    diagnostics: ScanDiagnostics | None = None,
) -> int:
    total_size = human_size(sum(t.size for t in targets))
    total_label = "at least " if any(not target.size_complete for target in targets) else ""
    print(f"\nAbout to delete {len(targets)} folder(s) totaling {total_label}{total_size}:")
    print(format_targets_table(targets, diagnostics=diagnostics))
    print("\nWARNING: This permanently deletes these folders. They cannot be restored from Trash or Recycle Bin.")
    if not yes:
        try:
            answer = input("Type 'delete' to permanently delete these folders, or press Enter to cancel: ").strip().lower()
        except EOFError:
            answer = ""
        if answer != "delete":
            print("Aborted.")
            return 0

    succeeded: list[ScanTarget] = []
    failed: list[tuple[ScanTarget, str]] = []
    for target in targets:
        try:
            delete_tree(target.path)
            succeeded.append(target)
            print(f"  Deleted  {target.path}")
        except Exception as exc:
            failed.append((target, str(exc)))
            print(f"  FAILED   {target.path}  ({exc})")

    print(f"\nDeleted {len(succeeded)}/{len(targets)} folder(s).")
    if failed:
        print(f"{len(failed)} deletion(s) failed — see above for details.")

    if json_out:
        payload = {
            "deleted_count": len(succeeded),
            "failed_count": len(failed),
            "total_size_bytes": sum(t.size for t in succeeded),
            "total_size_complete": not any(not target.size_complete for target in succeeded),
            "scan_complete": not diagnostics.incomplete if diagnostics is not None else True,
            "scan_errors": diagnostics.errors if diagnostics is not None else [],
            "scan_error_count": diagnostics.error_count if diagnostics is not None else 0,
            "deleted": serialize_targets(succeeded),
            "failed": [{"path": str(t.path), "error": err} for t, err in failed],
        }
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report written to {json_out}")

    return 0 if not failed else 1


def write_json_report(
    targets: list[ScanTarget],
    output_path: Path,
    diagnostics: ScanDiagnostics | None = None,
) -> None:
    payload = {
        "count": len(targets),
        "total_size_bytes": sum(target.size for target in targets),
        "total_size_complete": not any(not target.size_complete for target in targets)
        and not (diagnostics is not None and diagnostics.incomplete),
        "targets": serialize_targets(targets),
        "scan_complete": not diagnostics.incomplete if diagnostics is not None else True,
        "scan_errors": diagnostics.errors if diagnostics is not None else [],
        "scan_error_count": diagnostics.error_count if diagnostics is not None else 0,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
