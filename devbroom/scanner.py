from __future__ import annotations

import os
import threading
from pathlib import Path

from .models import (
    NODE_MODULES_NAME,
    SKIP_PARENT_NAMES,
    VENV_BIN_MARKERS,
    VENV_KIND,
    VENV_MARKERS,
    VENV_NAMES,
    ScanTarget,
)


def is_case_insensitive_filesystem() -> bool:
    return os.name == "nt"


def normalize_target_name(name: str) -> str:
    return name.casefold() if is_case_insensitive_filesystem() else name


def human_size(num_bytes: int) -> str:
    value = float(max(0, num_bytes))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024:
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} PB"


def is_skip_parent(path: Path) -> bool:
    parent_names = path.parts[:-1]
    if is_case_insensitive_filesystem():
        normalized = {part.casefold() for part in parent_names}
        return any(name.casefold() in normalized for name in SKIP_PARENT_NAMES)
    return any(name in parent_names for name in SKIP_PARENT_NAMES)


def is_virtualenv(path: Path) -> bool:
    if not path.is_dir():
        return False

    for marker in VENV_MARKERS:
        if (path / marker).exists():
            return True

    for bin_dir in VENV_BIN_MARKERS:
        if (path / bin_dir / "activate").exists():
            return True

    return False


def safe_folder_size(path: Path, stop_event: threading.Event | None = None) -> int:
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path, topdown=True, followlinks=False):
            if stop_event and stop_event.is_set():
                return total

            dirnames[:] = [name for name in dirnames if not Path(dirpath, name).is_symlink()]

            for filename in filenames:
                file_path = Path(dirpath, filename)
                try:
                    if file_path.is_symlink():
                        continue
                    total += file_path.stat().st_size
                except OSError:
                    continue
    except OSError:
        return total
    return total


def iter_scan_targets(root: Path, stop_event: threading.Event):
    visited_realpaths: set[str] = set()
    normalized_venv_names = {normalize_target_name(name) for name in VENV_NAMES}

    for dirpath, dirnames, _ in os.walk(root.expanduser(), topdown=True, followlinks=False):
        if stop_event.is_set():
            return

        pruned_names: list[str] = []
        for dirname in list(dirnames):
            candidate = Path(dirpath, dirname)

            try:
                if candidate.is_symlink():
                    pruned_names.append(dirname)
                    continue
            except OSError:
                pruned_names.append(dirname)
                continue

            realpath = os.path.realpath(candidate)
            if realpath in visited_realpaths:
                pruned_names.append(dirname)
                continue

            normalized_name = normalize_target_name(dirname)
            matched_kind: str | None = None

            if normalized_name == normalize_target_name(NODE_MODULES_NAME):
                matched_kind = NODE_MODULES_NAME
            elif normalized_name in normalized_venv_names:
                if not is_skip_parent(candidate) and is_virtualenv(candidate):
                    matched_kind = VENV_KIND

            if not matched_kind:
                continue

            visited_realpaths.add(realpath)
            pruned_names.append(dirname)
            yield ScanTarget(
                path=candidate,
                kind=matched_kind,
                size=safe_folder_size(candidate, stop_event),
            )

        for dirname in pruned_names:
            if dirname in dirnames:
                dirnames.remove(dirname)
