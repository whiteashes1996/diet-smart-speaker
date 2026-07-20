# Smart Speaker (Diet Voice Assistant)

Mac-first diet voice assistant: wake word → STT → DeepSeek (+ health MCP) → TTS. Modular Protocol/adapters architecture, portable to Raspberry Pi.

## Status

Task 0 baseline: Protocol definitions, config loading, error types, and pytest scaffolding.

## Setup

```bash
cd "/Users/whiteashes/Documents/智能音箱"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill DEEPSEEK_API_KEY, STT_*, MCP_HEALTH_COMMAND
cp config.yaml.example config.yaml  # optional non-secret defaults
```

## Configuration

Priority: **env > config.yaml > defaults**

| Field | Default | Env var |
|-------|---------|---------|
| wake_word | hey_jarvis | WAKE_WORD |
| sample_rate | 16000 | SAMPLE_RATE |
| silence_ms | 1200 | SILENCE_MS |
| max_listen_s | 30 | MAX_LISTEN_S |
| timezone | Asia/Shanghai | TIMEZONE |
| deepseek_api_key | — | DEEPSEEK_API_KEY |
| stt_api_key | — | STT_API_KEY |
| stt_base_url | — | STT_BASE_URL |
| mcp_health_command | — | MCP_HEALTH_COMMAND |

## Tests

```bash
pytest tests/test_protocols_import.py tests/test_config.py -v
```

## Manual gates (later tasks)

- Task 2 (Wake): human sign-off required before STT work
- Task 3 (STT): human sign-off required before Task 4+

## License

Private repository — not for public distribution.
