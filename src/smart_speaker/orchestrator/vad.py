"""Energy-based silence VAD for utterance end detection."""

from __future__ import annotations

import math
import struct


def is_speech(frame: bytes, threshold: int = 500) -> bool:
    """Return True if RMS energy of s16le mono frame exceeds threshold."""
    if len(frame) < 2:
        return False
    n = len(frame) // 2
    samples = struct.unpack(f"<{n}h", frame[: n * 2])
    if not samples:
        return False
    mean_sq = sum(s * s for s in samples) / len(samples)
    rms = math.sqrt(mean_sq)
    return rms >= threshold


class SilenceVAD:
    """Push PCM frames; returns 'continue' or 'end_utterance'."""

    def __init__(self, silence_ms: int = 1200, frame_ms: int = 40, threshold: int = 500) -> None:
        self._silence_ms = silence_ms
        self._frame_ms = frame_ms
        self._threshold = threshold
        self._silent_ms = 0
        self._heard_speech = False

    def reset(self) -> None:
        self._silent_ms = 0
        self._heard_speech = False

    def push(self, frame: bytes) -> str:
        if is_speech(frame, self._threshold):
            self._heard_speech = True
            self._silent_ms = 0
            return "continue"
        if not self._heard_speech:
            return "continue"
        self._silent_ms += self._frame_ms
        if self._silent_ms >= self._silence_ms:
            return "end_utterance"
        return "continue"
