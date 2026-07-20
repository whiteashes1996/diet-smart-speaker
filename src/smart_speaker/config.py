from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_ENV_FIELD_MAP: dict[str, str] = {
    "WAKE_WORD": "wake_word",
    "SAMPLE_RATE": "sample_rate",
    "SILENCE_MS": "silence_ms",
    "MAX_LISTEN_S": "max_listen_s",
    "TIMEZONE": "timezone",
    "DEEPSEEK_API_KEY": "deepseek_api_key",
    "STT_API_KEY": "stt_api_key",
    "STT_BASE_URL": "stt_base_url",
    "MCP_HEALTH_COMMAND": "mcp_health_command",
}

_INT_FIELDS = frozenset({"sample_rate", "silence_ms", "max_listen_s"})


@dataclass
class AppConfig:
    wake_word: str = "hey_jarvis"
    sample_rate: int = 16000
    silence_ms: int = 1200
    max_listen_s: int = 30
    timezone: str = "Asia/Shanghai"
    deepseek_api_key: str | None = None
    stt_api_key: str | None = None
    stt_base_url: str | None = None
    mcp_health_command: str | None = None


def _coerce_value(field: str, value: Any) -> Any:
    if field in _INT_FIELDS and value is not None:
        return int(value)
    if isinstance(value, str) and value == "":
        return None
    return value


def _apply_mapping(config: AppConfig, mapping: dict[str, Any]) -> None:
    for key, value in mapping.items():
        if value is None:
            continue
        if not hasattr(config, key):
            continue
        setattr(config, key, _coerce_value(key, value))


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def _load_env_overrides() -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for env_name, field_name in _ENV_FIELD_MAP.items():
        if env_name not in os.environ:
            continue
        overrides[field_name] = os.environ[env_name]
    return overrides


def load_config(
    yaml_path: Path | str | None = "config.yaml",
    env_file: Path | str | None = ".env",
) -> AppConfig:
    """Load config with priority: env > config.yaml > defaults."""
    if env_file is not None:
        load_dotenv(env_file, override=False)

    config = AppConfig()

    if yaml_path is not None:
        _apply_mapping(config, _load_yaml(Path(yaml_path)))

    _apply_mapping(config, _load_env_overrides())
    return config
