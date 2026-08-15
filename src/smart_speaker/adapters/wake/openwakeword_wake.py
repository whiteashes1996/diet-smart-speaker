"""OpenWakeWord-backed WakeWord adapter."""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

OWW_FRAME_SAMPLES = 1280  # 80 ms @ 16 kHz
DEFAULT_THRESHOLD = 0.75
DEFAULT_REFRACTORY_S = 4.0
CONSECUTIVE_HITS = 2


def _resolve_wakeword_model(model_name: str) -> str:
    """Prefer packaged ONNX when given a short name like hey_jarvis."""
    path = Path(model_name)
    if path.is_file():
        return str(path)
    try:
        import openwakeword
    except ImportError:
        return model_name
    models_dir = Path(openwakeword.__file__).parent / "resources" / "models"
    candidates = [
        models_dir / f"{model_name}_v0.1.onnx",
        models_dir / f"{model_name}.onnx",
        models_dir / model_name,
    ]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    return model_name


class OpenWakeWordWake:
    """Detect wake word via openWakeWord; time-based refractory after trigger."""

    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = DEFAULT_THRESHOLD,
        refractory_s: float = DEFAULT_REFRACTORY_S,
    ) -> None:
        from openwakeword.model import Model

        model_path = _resolve_wakeword_model(model_name)
        self._model = Model(wakeword_models=[model_path], inference_framework="onnx")
        self._threshold = threshold
        self._refractory_s = refractory_s
        self._cool_until = 0.0
        self._hits = 0
        self._buffer = np.zeros((0,), dtype=np.int16)
        self.last_score: float = 0.0

    def suppress(self, seconds: float | None = None) -> None:
        """Ignore wake detections for a while (after TTS / returning to idle)."""
        hold = self._refractory_s if seconds is None else seconds
        self._cool_until = max(self._cool_until, time.monotonic() + hold)
        self._hits = 0
        self._buffer = np.zeros((0,), dtype=np.int16)
        reset = getattr(self._model, "reset", None)
        if callable(reset):
            reset()

    def process_chunk(self, pcm: bytes) -> bool:
        if time.monotonic() < self._cool_until:
            return False

        audio = np.frombuffer(pcm, dtype=np.int16)
        if audio.size == 0:
            return False
        self._buffer = np.concatenate([self._buffer, audio])
        triggered = False
        while self._buffer.size >= OWW_FRAME_SAMPLES:
            frame = self._buffer[:OWW_FRAME_SAMPLES]
            self._buffer = self._buffer[OWW_FRAME_SAMPLES:]
            scores = self._model.predict(frame)
            score = float(max(scores.values())) if scores else 0.0
            self.last_score = score
            if score >= self._threshold:
                self._hits += 1
            else:
                self._hits = 0
            if self._hits >= CONSECUTIVE_HITS:
                self.suppress()
                triggered = True
                break
        return triggered
