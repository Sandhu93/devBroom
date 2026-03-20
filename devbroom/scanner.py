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


def normalize_path_for_compare(path: Path | str) -> str:
    normalized = os.path.realpath(Path(path))
    return normalized.casefold() if is_case_insensitive_filesystem() else normalized


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


def is_inside_git_repo(path: Path) -> bool:
    """Return True if path has a .git directory somewhere in its ancestry."""
    for parent in path.parents:
        if (parent / ".git").exists():
            return True
    return False


def is_ignored_path(path: Path, ignored_paths: set[str]) -> bool:
    candidate = normalize_path_for_compare(path)
    for ignored in ignored_paths:
        if candidate == ignored:
            return True
        if candidate.startswith(ignored + os.sep):
            return True
    return False


def iter_scan_targets(root: Path, stop_event: threading.Event, ignored_paths: list[str] | tuple[str, ...] | None = None, require_git_repo: bool = True):
    visited_realpaths: set[str] = set()
    normalized_venv_names = {normalize_target_name(name) for name in VENV_NAMES}
    ignored_roots = {normalize_path_for_compare(path) for path in (ignored_paths or [])}

    for dirpath, dirnames, _ in os.walk(root.expanduser(), topdown=True, followlinks=False):
        if stop_event.is_set():
            return
        current_path = Path(dirpath)
        if is_ignored_path(current_path, ignored_roots):
            dirnames[:] = []
            continue

        pruned_names: list[str] = []
        for dirname in list(dirnames):
            candidate = Path(dirpath, dirname)
            if is_ignored_path(candidate, ignored_roots):
                pruned_names.append(dirname)
                continue

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

            if require_git_repo and not is_inside_git_repo(candidate):
                pruned_names.append(dirname)
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
