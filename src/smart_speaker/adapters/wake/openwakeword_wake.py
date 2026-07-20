"""OpenWakeWord-backed WakeWord adapter."""

from __future__ import annotations

import numpy as np

REFRACTORY_CHUNKS = 50  # ~2s @ 40ms per chunk


class OpenWakeWordWake:
    """Detect wake word via openWakeWord; refractory period after trigger."""

    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5) -> None:
        from openwakeword.model import Model

        self._model = Model(wakeword_models=[model_name])
        self._threshold = threshold
        self._cooldown_chunks = 0

    def process_chunk(self, pcm: bytes) -> bool:
        if self._cooldown_chunks > 0:
            self._cooldown_chunks -= 1
            return False

        audio = np.frombuffer(pcm, dtype=np.int16)
        scores = self._model.predict(audio)
        score = float(max(scores.values())) if scores else 0.0
        if score >= self._threshold:
            self._cooldown_chunks = REFRACTORY_CHUNKS
            return True
        return False
