#!/usr/bin/env python3
"""Record ~3s from mic and play back (manual smoke test)."""

from __future__ import annotations

import sys
import time

from smart_speaker.adapters.audio.sounddevice_io import SoundDeviceAudioIO
from smart_speaker.config import load_config

RECORD_SECONDS = 3


def main() -> int:
    config = load_config()
    audio = SoundDeviceAudioIO(config)
    chunks: list[bytes] = []

    print(f"Recording {RECORD_SECONDS}s @ {config.sample_rate} Hz — speak now...")
    audio.start_input(chunks.append)
    time.sleep(RECORD_SECONDS)
    audio.stop_input()

    pcm = b"".join(chunks)
    if not pcm:
        print("No audio captured. Check microphone permissions.", file=sys.stderr)
        return 1

    print(f"Captured {len(pcm)} bytes. Playing back...")
    audio.play(pcm)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
