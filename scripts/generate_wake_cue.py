#!/usr/bin/env python3
"""Generate a short beep wake cue WAV file."""

from __future__ import annotations

import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16000
DURATION_S = 0.15
FREQUENCY_HZ = 880.0
AMPLITUDE = 0.4

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "wake_cue.wav"


def generate_beep_pcm() -> bytes:
    import math

    n_samples = int(SAMPLE_RATE * DURATION_S)
    samples: list[int] = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        envelope = min(1.0, t / 0.01, (DURATION_S - t) / 0.02)
        value = int(32767 * AMPLITUDE * envelope * math.sin(2 * math.pi * FREQUENCY_HZ * t))
        samples.append(value)
    return struct.pack(f"<{len(samples)}h", *samples)


def write_wav(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


def main() -> int:
    pcm = generate_beep_pcm()
    write_wav(OUTPUT, pcm)
    print(f"Wrote {OUTPUT} ({len(pcm)} bytes pcm)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
