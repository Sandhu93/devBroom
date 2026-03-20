from __future__ import annotations

import json
import threading
from pathlib import Path

from .models import ScanTarget
from .scanner import human_size, iter_scan_targets


def scan_targets(root: Path, ignored_paths: tuple[str, ...] = ()) -> list[ScanTarget]:
    stop_event = threading.Event()
    return list(iter_scan_targets(root, stop_event, ignored_paths=ignored_paths))


def serialize_targets(targets: list[ScanTarget]) -> list[dict[str, str | int]]:
    return [
        {
            "path": str(target.path),
            "kind": target.kind,
            "size_bytes": target.size,
            "size_human": human_size(target.size),
        }
        for target in targets
    ]


def format_targets_table(targets: list[ScanTarget]) -> str:
    if not targets:
        return "No cleanup targets found."

    rows = [
        ("TYPE", "SIZE", "PATH"),
        *[(target.kind, human_size(target.size), str(target.path)) for target in targets],
    ]

    type_width = max(len(row[0]) for row in rows)
    size_width = max(len(row[1]) for row in rows)

    lines = []
    for index, row in enumerate(rows):
        lines.append(f"{row[0]:<{type_width}}  {row[1]:>{size_width}}  {row[2]}")
        if index == 0:
            lines.append(f"{'-' * type_width}  {'-' * size_width}  {'-' * 4}")

    total_size = sum(target.size for target in targets)
    lines.append("")
    lines.append(f"Found {len(targets)} folders totaling {human_size(total_size)}.")
    return "\n".join(lines)


def write_json_report(targets: list[ScanTarget], output_path: Path) -> None:
    payload = {
        "count": len(targets),
        "total_size_bytes": sum(target.size for target in targets),
        "targets": serialize_targets(targets),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
