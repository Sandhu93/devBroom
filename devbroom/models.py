from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


NODE_MODULES_NAME = "node_modules"
VENV_KIND = "venv"
# "env" is intentionally excluded: it is too generic a name to match safely.
# Many projects use env/ for non-venv purposes (config dirs, Docker env files,
# etc.), so including it would risk deleting unrelated directories. Users who
# name their virtual environment "env" can add it to their ignored-paths list
# as a workaround if needed.
VENV_NAMES = {"venv", ".venv", "virtualenv"}
VENV_MARKERS = {"pyvenv.cfg"}
VENV_BIN_MARKERS = {"Scripts", "bin"}
SKIP_PARENT_NAMES = {"site-packages", "Lib", "lib", NODE_MODULES_NAME}


@dataclass(frozen=True)
class ScanTarget:
    path: Path
    kind: str
    size: int
