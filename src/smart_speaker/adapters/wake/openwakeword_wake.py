"""OpenWakeWord-backed WakeWord adapter."""

from __future__ import annotations

from pathlib import Path

import numpy as np

REFRACTORY_CHUNKS = 25  # ~2s @ 80ms per chunk
OWW_FRAME_SAMPLES = 1280  # 80 ms @ 16 kHz


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
    """Detect wake word via openWakeWord; refractory period after trigger."""

    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5) -> None:
        from openwakeword.model import Model

        model_path = _resolve_wakeword_model(model_name)
        self._model = Model(wakeword_models=[model_path], inference_framework="onnx")
        self._threshold = threshold
        self._cooldown_chunks = 0
        self._buffer = np.zeros((0,), dtype=np.int16)
        self.last_score: float = 0.0

    def process_chunk(self, pcm: bytes) -> bool:
        if self._cooldown_chunks > 0:
            self._cooldown_chunks -= 1
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
                self._cooldown_chunks = REFRACTORY_CHUNKS
                self._buffer = np.zeros((0,), dtype=np.int16)
                triggered = True
                break
        return triggered
