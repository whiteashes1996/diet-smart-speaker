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
| Tools | MCP stdio | same command pointing at health DB |

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
