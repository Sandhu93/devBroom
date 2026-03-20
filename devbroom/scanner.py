from __future__ import annotations

import os
import threading
import time
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


def human_age(days: float) -> str:
    if days < 1:
        return "< 1d"
    if days < 30:
        return f"{int(days)}d"
    if days < 365:
        return f"{int(days / 30)}mo"
    return f"{days / 365:.1f}yr"


def _calc_age_days(path: Path, kind: str) -> float:
    """Return how many days ago the target was last meaningfully modified.

    For virtualenvs, also checks Scripts/ and bin/ since pip updates those
    subdirectories when installing packages, not the venv root itself.
    Returns 0.0 on any OS error or if the mtime is in the future (clock skew).
    """
    try:
        mtime = os.path.getmtime(path)
        if kind == VENV_KIND:
            for sub in ("Scripts", "bin"):
                try:
                    mtime = max(mtime, os.path.getmtime(path / sub))
                except OSError:
                    pass
        return max(0.0, (time.time() - mtime) / 86400)
    except OSError:
        return 0.0


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


def iter_scan_targets(
    root: Path,
    stop_event: threading.Event,
    ignored_paths: list[str] | tuple[str, ...] | None = None,
    require_git_repo: bool = True,
    older_than: int | None = None,
    stats: dict | None = None,
):
    visited_realpaths: set[str] = set()
    normalized_venv_names = {normalize_target_name(name) for name in VENV_NAMES}
    ignored_roots = {normalize_path_for_compare(path) for path in (ignored_paths or [])}

    for dirpath, dirnames, _ in os.walk(root.expanduser(), topdown=True, followlinks=False):
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

            age_days = _calc_age_days(candidate, matched_kind)
            if older_than is not None and older_than > 0 and age_days < older_than:
                pruned_names.append(dirname)
                continue

            visited_realpaths.add(realpath)
            pruned_names.append(dirname)
            yield ScanTarget(
                path=candidate,
                kind=matched_kind,
                size=safe_folder_size(candidate, stop_event),
                age_days=age_days,
            )

        for dirname in pruned_names:
            if dirname in dirnames:
                dirnames.remove(dirname)
