# Raspberry Pi / Linux port notes

Target: Raspberry Pi 5 with **8GB** RAM (or similar aarch64 Linux).

## Same orchestrator

Do **not** fork business logic. Swap adapters only:

| Protocol | Mac v1 | Pi suggestion |
|----------|--------|----------------|
| AudioIO | sounddevice | sounddevice + PortAudio (`libportaudio2`) |
| WakeWord | openWakeWord | same (onnxruntime) |
| STT | cloud Whisper API | cloud first; later faster-whisper |
| LLM | DeepSeek cloud | keep cloud on 8GB Pi (local LLM is optional later) |
| TTS | edge-tts (+ ffmpeg for PCM) | Piper local later |
| Tools | MCP stdio | Remote streamable-HTTP (`MCP_HEALTH_URL` + user token); stdio only as fallback |

## Remote health MCP

On the Pi, put these in `.env` (do not commit):

```bash
MCP_HEALTH_URL=https://47.94.4.180:8443/mcp
MCP_HEALTH_TOKEN=  # user1 Bearer token; identity is bound to the token
# MCP_HEALTH_CA_FILE=~/health-mcp-ca.pem
NO_PROXY=47.94.4.180
```

Copy the CA file onto the Pi if the server uses a self-signed cert. Diet writes go only to the remote MCP; local notes stay in `~/smart-speaker/memory/notes.jsonl`.

Smoke (text only, no mic):

```bash
python scripts/manual_mcp_log_food.py --name 鸡蛋 --pieces 2 --meal 午
```

## Install hints (Debian/Ubuntu aarch64)

```bash
sudo apt update
sudo apt install -y python3-venv python3-dev portaudio19-dev ffmpeg
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Mic / permissions

- Prefer USB mic; set default ALSA device if needed (`~/.asoundrc`).
- Run headless under systemd user service after smoke tests.

## Performance

- Keep LLM/STT on cloud for acceptable latency.
- Log stage timings: wake / stt_ms / llm / tts (already partially logged).

## Sanity scan

```bash
rg -n "AppKit|AVFoundation|import objc" src || true
```

Expect no matches — codebase is cross-platform Python.
