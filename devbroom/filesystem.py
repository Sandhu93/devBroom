from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Callable


def is_link_or_junction(
    path: Path, on_error: Callable[[Path, OSError], None] | None = None
) -> bool:
    """Return True for symlinks, Windows junctions, or unknown reparse points.

    On Windows, checking the reparse-point attribute also works on Python
    versions before ``Path.is_junction`` was added. If the path cannot be
    inspected, treat it as unsafe so scanners and deletion fail closed.
    """
    try:
        if path.is_symlink():
            return True

        is_junction = getattr(path, "is_junction", None)
        if is_junction is not None and is_junction():
            return True

        if os.name == "nt":
            attributes = getattr(path.lstat(), "st_file_attributes", 0)
            reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            return bool(attributes & reparse_point)
    except OSError as exc:
        if on_error is not None:
            on_error(path, exc)
        return True

    return False
