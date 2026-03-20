from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


SETTINGS_ENV_VAR = "DEVBROOM_SETTINGS_FILE"
DEFAULT_SETTINGS_FILENAME = ".devbroom.json"


@dataclass(frozen=True)
class AppSettings:
    last_path: str = ""
    theme: str = "dark"


def settings_file_path() -> Path:
    override = os.environ.get(SETTINGS_ENV_VAR)
    if override:
        return Path(override).expanduser()
    return Path.home() / DEFAULT_SETTINGS_FILENAME


def load_settings(path: Path | None = None) -> AppSettings:
    target = path or settings_file_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    theme = raw.get("theme", "dark")
    if theme not in {"light", "dark"}:
        theme = "dark"

    last_path = raw.get("last_path", "")
    if not isinstance(last_path, str):
        last_path = ""

    return AppSettings(last_path=last_path, theme=theme)


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    target = path or settings_file_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(settings), indent=2)
    target.write_text(payload + "\n", encoding="utf-8")
