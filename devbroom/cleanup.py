from __future__ import annotations

import os
import stat
from pathlib import Path


def _on_rm_error(_func, path: str, exc_info) -> None:
    del exc_info
    os.chmod(path, stat.S_IWRITE)
    _func(path)


def delete_tree(path: Path) -> None:
    if not path.exists():
        return
    if path.is_symlink():
        raise OSError(f"Refusing to delete symlink target: {path}")

    import shutil

    shutil.rmtree(path, onerror=_on_rm_error)
