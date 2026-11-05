"""ユーザー設定の保存 — 読めない・書けない場合は既定値のまま動く"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from ai import CPU_DIFFICULTY_ORDER, DEFAULT_CPU_DIFFICULTY

SETTINGS_DIR_NAME = "ImomushiHockey"
SETTINGS_FILE_NAME = "settings.json"


@dataclass
class Settings:
    bgm_muted: bool = False
    fullscreen: bool = False
    cpu_difficulty: str = DEFAULT_CPU_DIFFICULTY

    @property
    def cpu_diff_index(self) -> int:
        return CPU_DIFFICULTY_ORDER.index(self.cpu_difficulty)


def settings_path() -> Path:
    override = os.environ.get("IMOMUSHI_SETTINGS_DIR")
    if override:
        return Path(override) / SETTINGS_FILE_NAME
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME


def load_settings() -> Settings:
    settings = Settings()
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings
    if not isinstance(data, dict):
        return settings
    if isinstance(data.get("bgm_muted"), bool):
        settings.bgm_muted = data["bgm_muted"]
    if isinstance(data.get("fullscreen"), bool):
        settings.fullscreen = data["fullscreen"]
    difficulty = data.get("cpu_difficulty")
    if isinstance(difficulty, str) and difficulty in CPU_DIFFICULTY_ORDER:
        settings.cpu_difficulty = difficulty
    return settings


def save_settings(settings: Settings) -> bool:
    path = settings_path()
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        return False
    return True
