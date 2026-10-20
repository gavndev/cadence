from __future__ import annotations

import json
import os
from pathlib import Path


def config_dir() -> Path:
    raw = os.environ.get("CADENCE_CONFIG", "./data")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _settings_file() -> Path:
    return config_dir() / "library.json"


def builtin_library() -> Path:
    raw = os.environ.get("CADENCE_BUILTIN_LIBRARY") or os.environ.get("MUSIC_LIBRARY", "./library")
    return Path(raw).expanduser().resolve()


def builtin_label() -> str:
    return os.environ.get("CADENCE_BUILTIN_LABEL") or str(builtin_library())


def load_settings() -> dict | None:
    file = _settings_file()
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not data.get("path"):
        return None
    return data


def is_configured() -> bool:
    return load_settings() is not None


def resolved_library() -> Path:
    saved = load_settings()
    if saved:
        return Path(str(saved["path"])).expanduser().resolve()
    return builtin_library()


def _write(mode: str, path: Path) -> None:
    payload = {"mode": mode, "path": str(path)}
    _settings_file().write_text(json.dumps(payload), encoding="utf-8")


def save_builtin() -> Path:
    path = builtin_library()
    path.mkdir(parents=True, exist_ok=True)
    _write("builtin", path)
    return path


def save_custom(raw: str) -> Path:
    text = (raw or "").strip()
    if not text:
        raise ValueError("Enter the folder path on the server")
    path = Path(text).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(
            "That folder isn't on the server yet. Create it first, or use the built-in library."
        )
    _write("custom", path)
    return path
