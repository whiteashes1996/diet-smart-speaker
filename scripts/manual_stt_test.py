#!/usr/bin/env python3
"""Manual STT gate: wake → record until silence → Whisper STT."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_speaker.adapters.audio.sounddevice_io import SoundDeviceAudioIO
from smart_speaker.adapters.stt.openai_whisper_stt import OpenAIWhisperSTT
from smart_speaker.adapters.wake.openwakeword_wake import OpenWakeWordWake
from smart_speaker.config import load_config
from smart_speaker.errors import TransientError
from smart_speaker.orchestrator.vad import SilenceVAD
from smart_speaker.orchestrator.state_machine import load_wake_cue_pcm

LOG = Path("/tmp/smart-speaker-stt-manual.log")


def main() -> int:
    cfg = load_config()
    if not cfg.stt_api_key:
        print("STT_API_KEY missing in .env", file=sys.stderr)
        return 1
    cue_path = ROOT / "assets" / "wake_cue.wav"
    cue = load_wake_cue_pcm(cue_path) if cue_path.is_file() else b"\x00\x00" * 800

    audio = SoundDeviceAudioIO(sample_rate=cfg.sample_rate)
    wake = OpenWakeWordWake(model_name=cfg.wake_word)
    stt = OpenAIWhisperSTT(
        api_key=cfg.stt_api_key,
        base_url=cfg.stt_base_url or "https://api.openai.com/v1",
        model=cfg.stt_model,
        sample_rate=cfg.sample_rate,
    )
    vad = SilenceVAD(silence_ms=cfg.silence_ms, frame_ms=40)
    buf = bytearray()
    state = "idle"
    listen_t0 = 0.0
    done = asyncio.Event()
    result_holder: dict = {}

    print(f"请说 {cfg.wake_word}，听到提示音后说中文短句（如：今天中午吃了鸡蛋）")

    def on_chunk(pcm: bytes) -> None:
        nonlocal state, listen_t0
        if state == "idle":
            if wake.process_chunk(pcm):
                state = "listening"
                listen_t0 = time.monotonic()
                vad.reset()
                buf.clear()
                audio.set_capture_enabled(False)
                audio.play(cue)
                audio.set_capture_enabled(True)
                print("WAKE_OK — 请说话…")
            return
        if state == "listening":
            buf.extend(pcm)
            if time.monotonic() - listen_t0 >= cfg.max_listen_s:
                state = "done"
                done.set()
                return
            if vad.push(pcm) == "end_utterance":
                state = "done"
                done.set()

    async def run() -> int:
        audio.start_input(on_chunk)
        try:
            try:
                await asyncio.wait_for(done.wait(), timeout=90)
            except TimeoutError:
                print("STT_TIMEOUT")
                LOG.write_text("TIMEOUT\n")
                return 2
            audio.set_capture_enabled(False)
            pcm = bytes(buf)
            t0 = time.perf_counter()
            try:
                text = await stt.transcribe(pcm)
            except TransientError as exc:
                print(f"STT_ERROR={exc}")
                LOG.write_text(f"ERROR {exc}\n")
                return 3
            ms = int((time.perf_counter() - t0) * 1000)
            print(f"STT_TEXT=<<{text}>>")
            print(f"STT_MS={ms}")
            LOG.write_text(f"TEXT={text}\nMS={ms}\n")
            return 0
        finally:
            audio.stop_input()

    return asyncio.run(run())


if __name__ == "__main__":
    raise SystemExit(main())
