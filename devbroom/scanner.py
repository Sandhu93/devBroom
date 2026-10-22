from __future__ import annotations

import os
import stat
import threading
import time
from pathlib import Path

from .filesystem import is_link_or_junction
from .models import (
    NODE_MODULES_NAME,
    SKIP_PARENT_NAMES,
    VENV_BIN_MARKERS,
    VENV_KIND,
    VENV_MARKERS,
    VENV_NAMES,
    ScanDiagnostics,
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


def human_age(days: float | None) -> str:
    if days is None:
        return "Unknown"
    if days < 1:
        return "< 1d"
    if days < 30:
        return f"{int(days)}d"
    if days < 365:
        return f"{int(days / 30)}mo"
    return f"{days / 365:.1f}yr"


def is_skip_parent(path: Path) -> bool:
    parent_names = path.parts[:-1]
    if is_case_insensitive_filesystem():
        normalized = {part.casefold() for part in parent_names}
        return any(name.casefold() in normalized for name in SKIP_PARENT_NAMES)
    return any(name in parent_names for name in SKIP_PARENT_NAMES)


def is_virtualenv(path: Path, diagnostics: ScanDiagnostics | None = None) -> bool:
    try:
        if not stat.S_ISDIR(path.stat().st_mode):
            return False
    except FileNotFoundError:
        return False
    except OSError as exc:
        if diagnostics is not None:
            diagnostics.record(path, exc)
        return False

    def marker_exists(marker: Path) -> bool:
        try:
            marker.stat()
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            if diagnostics is not None:
                diagnostics.record(marker, exc)
            return False

    for marker in VENV_MARKERS:
        if marker_exists(path / marker):
            return True

    for bin_dir in VENV_BIN_MARKERS:
        if marker_exists(path / bin_dir / "activate"):
            return True

    return False


def safe_folder_stats(
    path: Path,
    stop_event: threading.Event | None = None,
    diagnostics: ScanDiagnostics | None = None,
) -> tuple[int, float | None]:
    """Return total file bytes and days since the newest mtime in the tree.

    Modification time is only a rough indicator of change; it cannot tell
    whether someone has recently used a folder. Symlink contents are ignored.
    """
    total = 0
    now = time.time()
    newest_mtime = 0.0
    errors_before = diagnostics.error_count if diagnostics else 0

    def record_error(error_path: Path | str, error: OSError) -> None:
        if diagnostics is not None:
            diagnostics.record(error_path, error)

    def on_walk_error(error: OSError) -> None:
        record_error(error.filename or path, error)

    try:
        for dirpath, dirnames, filenames in os.walk(
            path, topdown=True, onerror=on_walk_error, followlinks=False
        ):
            if stop_event and stop_event.is_set():
                return total, None

            current_path = Path(dirpath)
            try:
                newest_mtime = max(newest_mtime, current_path.stat().st_mtime)
            except OSError as exc:
                record_error(current_path, exc)

            kept_dirnames = []
            for name in dirnames:
                child = current_path / name
                if is_link_or_junction(child, on_error=record_error):
                    continue
                kept_dirnames.append(name)
                try:
                    newest_mtime = max(newest_mtime, child.stat().st_mtime)
                except OSError as exc:
                    record_error(child, exc)
            dirnames[:] = kept_dirnames

            for filename in filenames:
                file_path = current_path / filename
                try:
                    if is_link_or_junction(file_path, on_error=record_error):
                        continue
                    file_stat = file_path.stat()
                    total += file_stat.st_size
                    newest_mtime = max(newest_mtime, file_stat.st_mtime)
                except OSError as exc:
                    record_error(file_path, exc)
                    continue
    except OSError as exc:
        record_error(path, exc)
    if diagnostics is not None and diagnostics.error_count > errors_before:
        return total, None
    age_days = max(0.0, (now - newest_mtime) / 86400) if newest_mtime else 0.0
    return total, age_days


def safe_folder_size(path: Path, stop_event: threading.Event | None = None) -> int:
    """Return the total size of regular files beneath a folder."""
    size, _age_days = safe_folder_stats(path, stop_event)
    return size


def is_inside_git_repo(path: Path, diagnostics: ScanDiagnostics | None = None) -> bool:
    """Return True if path has a .git directory somewhere in its ancestry."""
    for parent in path.parents:
        git_marker = parent / ".git"
        try:
            git_marker.stat()
            return True
        except FileNotFoundError:
            continue
        except OSError as exc:
            if diagnostics is not None:
                diagnostics.record(git_marker, exc)
            return False
    return False


def is_ignored_path(path: Path, ignored_paths: set[str]) -> bool:
    candidate = normalize_path_for_compare(path)
    for ignored in ignored_paths:
        if candidate == ignored:
            return True
        if candidate.startswith(ignored + os.sep):
            return True
    return False


def iter_scan_targets(
    root: Path,
    stop_event: threading.Event,
    ignored_paths: list[str] | tuple[str, ...] | None = None,
    require_git_repo: bool = True,
    older_than: int | None = None,
    stats: dict | None = None,
    diagnostics: ScanDiagnostics | None = None,
):
    diagnostics = diagnostics if diagnostics is not None else ScanDiagnostics()

    def on_walk_error(error: OSError) -> None:
        diagnostics.record(error.filename or root, error)

    visited_realpaths: set[str] = set()
    normalized_venv_names = {normalize_target_name(name) for name in VENV_NAMES}
    ignored_roots = {normalize_path_for_compare(path) for path in (ignored_paths or [])}

    for dirpath, dirnames, _ in os.walk(
        root.expanduser(), topdown=True, onerror=on_walk_error, followlinks=False
    ):
        if stats is not None:
            stats["visited"] += 1
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
                if is_link_or_junction(candidate, on_error=diagnostics.record):
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
                if not is_skip_parent(candidate) and is_virtualenv(candidate, diagnostics):
                    matched_kind = VENV_KIND

            if not matched_kind:
                continue

            if require_git_repo and not is_inside_git_repo(candidate, diagnostics):
                pruned_names.append(dirname)
                continue

            errors_before = diagnostics.error_count
            size, age_days = safe_folder_stats(candidate, stop_event, diagnostics)
            size_complete = diagnostics.error_count == errors_before
            if (
                older_than is not None
                and older_than > 0
                and age_days is not None
                and age_days < older_than
            ):
                pruned_names.append(dirname)
                continue

            visited_realpaths.add(realpath)
            pruned_names.append(dirname)
            yield ScanTarget(
                path=candidate,
                kind=matched_kind,
                size=size,
                age_days=age_days,
                size_complete=size_complete,
            )

        for dirname in pruned_names:
            if dirname in dirnames:
                dirnames.remove(dirname)
