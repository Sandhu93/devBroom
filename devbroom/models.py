from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


NODE_MODULES_NAME = "node_modules"
VENV_KIND = "venv"
VENV_NAMES = {"venv", ".venv", "virtualenv"}
VENV_MARKERS = {"pyvenv.cfg"}
VENV_BIN_MARKERS = {"Scripts", "bin"}
SKIP_PARENT_NAMES = {"site-packages", "Lib", "lib", NODE_MODULES_NAME}


@dataclass(frozen=True)
class ScanTarget:
    path: Path
    kind: str
    size: int
