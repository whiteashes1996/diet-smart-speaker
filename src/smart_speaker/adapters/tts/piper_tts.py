"""Piper TTS adapter → pcm_s16le mono (local, on Pi).

Uses the Python ``piper`` API (piper-tts >= 1.6) so newer zh voices like
chaowen/xiao_ya (with multi-codepoint phonemes) work, unlike the older 1.2
binary. Forces offline mode for the bundled g2pW/BERT assets.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from smart_speaker.errors import FatalError, TransientError

logger = logging.getLogger(__name__)

# piper phonemize_chinese fetches g2pW/BERT from HF at runtime; we ship them
# locally on the Pi and pin HF offline so startup never blocks on the network.
os.environ.setdefault("HF_HUB_OFFLINE", "1")


class PiperTTS:
    """Local TTS via piper-tts Python API."""

    def __init__(
        self,
        piper_bin: Path | str | None = None,  # kept for config back-compat; unused
        model_path: Path | str = "",
        sample_rate: int = 16000,
        speaker: str | None = None,
    ) -> None:
        model = Path(model_path).expanduser()
        if not model.is_file():
            raise FatalError(f"Piper model not found: {model}")
        try:
            from piper import PiperVoice
        except ImportError as exc:
            raise FatalError("piper-tts is required for PiperTTS") from exc
        self._sample_rate = sample_rate
        self._speaker = speaker
        self._voice = PiperVoice.load(str(model))
        logger.info("Piper loaded: %s", model)

    def _resample(self, pcm: bytes, src_rate: int) -> bytes:
        if src_rate == self._sample_rate:
            return pcm
        import numpy as np

        arr = np.frombuffer(pcm, dtype=np.int16)
        if arr.size < 2:
            return pcm
        n_out = int(round(arr.shape[0] * self._sample_rate / float(src_rate)))
        if n_out < 1:
            return pcm
        x = np.arange(arr.shape[0], dtype=np.float64)
        xq = np.linspace(0.0, float(arr.shape[0] - 1), n_out)
        return (
            np.interp(xq, x, arr.astype(np.float64)).round().astype(np.int16).tobytes()
        )

    def _synthesize_sync(self, text: str) -> bytes:
        chunks: list[bytes] = []
        for chunk in self._voice.synthesize(text):
            chunks.append(chunk.audio_int16_bytes)
        pcm = b"".join(chunks)
        return self._resample(pcm, int(self._voice.config.sample_rate))

    async def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            raise TransientError("empty TTS text")
        try:
            pcm = await asyncio.to_thread(self._synthesize_sync, text)
        except TransientError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"Piper synthesize failed: {exc}") from exc
        logger.info("piper_pcm_bytes=%s", len(pcm))
        return pcm
