# Smart Speaker (Diet Voice Assistant)

Mac-first diet voice assistant: **wake → STT → DeepSeek (+ health MCP) → TTS**.  
Protocol/adapters architecture; portable to Raspberry Pi (8GB).

Private repo: https://github.com/whiteashes1996/diet-smart-speaker

## Setup (Mac)

```bash
cd "/Users/whiteashes/Documents/智能音箱"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# fill DEEPSEEK_API_KEY, STT_API_KEY, STT_BASE_URL
# fill MCP_HEALTH_URL + MCP_HEALTH_TOKEN (or MCP_HEALTH_COMMAND for local stdio)
# optional: brew install ffmpeg   # needed for EdgeTTS → PCM in the live loop
```

Grant **Microphone** permission to Terminal/iTerm when prompted.

## Run

```bash
source .venv/bin/activate
smart-speaker
# or: python -m smart_speaker
```

Say `hey jarvis` → cue beep → speak (e.g. diet log / ask advice) → hear reply.

## Configuration

Priority: **env > config.yaml > defaults**

| Field | Env |
|-------|-----|
| wake_word (`hey_jarvis`) | `WAKE_WORD` |
| STT | `STT_API_KEY`, `STT_BASE_URL`, `STT_MODEL` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Health MCP HTTP | `MCP_HEALTH_URL`, `MCP_HEALTH_TOKEN` (or `MCP_HEALTH_TOKEN_FILE`), `MCP_HEALTH_CA_FILE` |
| Health MCP stdio fallback | `MCP_HEALTH_COMMAND`（未设 URL 时） |

## Manual module gates

See [docs/manual-gates.md](docs/manual-gates.md).

```bash
python scripts/manual_audio_smoke.py   # mic loopback
python scripts/manual_wake_test.py     # wake hard gate
python scripts/manual_stt_test.py      # STT hard gate (needs STT_*)
python scripts/manual_tts_listen.py --text "已记录两个鸡蛋"
python scripts/manual_mcp_log_food.py --name 鸡蛋 --pieces 2 --meal 午
```

## Tests

```bash
pytest -v
```

Orchestrator must not import cloud SDKs (`tests/test_orchestrator_no_cloud_imports.py`).

## Raspberry Pi / Linux

See [docs/pi-port.md](docs/pi-port.md).

## Architecture

- `protocols/` — AudioIO, WakeWord, STT, LLM, TTS, ToolBackend
- `adapters/` — sounddevice, openWakeWord, Whisper API, DeepSeek, edge-tts, MCP
- `orchestrator/` — Idle → Listening → Thinking → Speaking (half-duplex)

Diet tools whitelist only: `log_food`, `list_foods`, `add_food`, `get_day`, `get_daily_summary`, `get_goals`, `get_trend`, `update_entry`, `delete_entry`.
