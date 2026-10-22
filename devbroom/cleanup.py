from __future__ import annotations

import os
import stat
from pathlib import Path

from .filesystem import is_link_or_junction


def _on_rm_error(_func, path: str, exc_info) -> None:
    del exc_info
    os.chmod(path, stat.S_IWRITE)
    _func(path)


def delete_tree(path: Path) -> None:
    if not path.exists():
        return
    if is_link_or_junction(path):
        raise OSError(f"Refusing to delete a symlink, junction, or reparse point: {path}")

    import shutil

    shutil.rmtree(path, onerror=_on_rm_error)
