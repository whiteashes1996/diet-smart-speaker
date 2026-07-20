from pathlib import Path

import pytest

from smart_speaker.config import AppConfig, load_config


def test_app_config_defaults():
    cfg = AppConfig()
    assert cfg.wake_word == "hey_jarvis"
    assert cfg.sample_rate == 16000
    assert cfg.silence_ms == 1200
    assert cfg.max_listen_s == 30
    assert cfg.timezone == "Asia/Shanghai"
    assert cfg.deepseek_api_key is None
    assert cfg.stt_api_key is None
    assert cfg.stt_base_url is None
    assert cfg.mcp_health_command is None


def test_yaml_loads_non_secret_defaults(tmp_path: Path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "wake_word: custom_wake\n"
        "sample_rate: 22050\n"
        "silence_ms: 800\n"
        "max_listen_s: 15\n"
        "timezone: UTC\n",
        encoding="utf-8",
    )

    cfg = load_config(yaml_path=yaml_path, env_file=None)

    assert cfg.wake_word == "custom_wake"
    assert cfg.sample_rate == 22050
    assert cfg.silence_ms == 800
    assert cfg.max_listen_s == 15
    assert cfg.timezone == "UTC"


def test_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "wake_word: from_yaml\n"
        "sample_rate: 22050\n"
        "stt_base_url: https://yaml.example/v1\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("WAKE_WORD", "from_env")
    monkeypatch.setenv("STT_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test")
    monkeypatch.setenv("MCP_HEALTH_COMMAND", "/bin/health-mcp")

    cfg = load_config(yaml_path=yaml_path, env_file=None)

    assert cfg.wake_word == "from_env"
    assert cfg.sample_rate == 22050
    assert cfg.stt_base_url == "https://yaml.example/v1"
    assert cfg.stt_api_key == "sk-test"
    assert cfg.deepseek_api_key == "ds-test"
    assert cfg.mcp_health_command == "/bin/health-mcp"
