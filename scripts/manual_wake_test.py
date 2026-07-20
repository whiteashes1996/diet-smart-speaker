#!/usr/bin/env python3
"""Manual wake-word test: mic → OpenWakeWord → beep on detection."""

from __future__ import annotations

import logging
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from smart_speaker.adapters.audio.sounddevice_io import SoundDeviceAudioIO
from smart_speaker.adapters.wake.openwakeword_wake import OpenWakeWordWake
from smart_speaker.config import load_config

LOG_PATH = Path("/tmp/smart-speaker-wake-manual.log")
WAKE_CUE_PATH = Path(__file__).resolve().parent.parent / "assets" / "wake_cue.wav"
TIMEOUT_S = 60


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, mode="w"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def load_wake_cue() -> bytes:
    if not WAKE_CUE_PATH.is_file():
        raise FileNotFoundError(
            f"Wake cue not found at {WAKE_CUE_PATH}. Run: python scripts/generate_wake_cue.py"
        )
    import wave

    with wave.open(str(WAKE_CUE_PATH), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError("wake_cue.wav must be mono pcm_s16le")
        return wf.readframes(wf.getnframes())


def main() -> int:
    setup_logging()
    log = logging.getLogger(__name__)

    config = load_config()
    audio = SoundDeviceAudioIO(config)
    wake = OpenWakeWordWake(model_name=config.wake_word)
    wake_cue = load_wake_cue()

    detected = threading.Event()
    result: dict[str, str] = {}

    def on_chunk(pcm: bytes) -> None:
        if detected.is_set():
            return
        if wake.process_chunk(pcm):
            detected.set()
            result["ts"] = datetime.now().isoformat(timespec="milliseconds")

    print("请说 hey jarvis。检测到会播放提示音并在终端打印 WAKE_OK")
    log.info("Starting wake test (timeout=%ds, model=%s)", TIMEOUT_S, config.wake_word)

    audio.start_input(on_chunk)
    deadline = time.monotonic() + TIMEOUT_S
    try:
        while time.monotonic() < deadline:
            if detected.wait(timeout=0.1):
                break
    finally:
        audio.stop_input()

    if not detected.is_set():
        print("WAKE_TIMEOUT")
        log.warning("Wake test timed out after %ds", TIMEOUT_S)
        return 2

    audio.set_capture_enabled(False)
    audio.play(wake_cue)
    ts = result["ts"]
    print(f"WAKE_OK {ts}")
    log.info("Wake detected at %s", ts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
