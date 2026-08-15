"""SenseVoice STT via sherpa-onnx (local, on Pi)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import numpy as np

from smart_speaker.errors import FatalError, TransientError

logger = logging.getLogger(__name__)


class SenseVoiceSTT:
    """Offline recognizer using sherpa-onnx SenseVoice int8 model."""

    def __init__(
        self,
        model_path: Path | str,
        tokens_path: Path | str,
        sample_rate: int = 16000,
        num_threads: int = 4,
        language: str = "auto",
        use_itn: bool = True,
    ) -> None:
        model_path = Path(model_path).expanduser()
        tokens_path = Path(tokens_path).expanduser()
        if not model_path.is_file():
            raise FatalError(f"SenseVoice model not found: {model_path}")
        if not tokens_path.is_file():
            raise FatalError(f"SenseVoice tokens not found: {tokens_path}")
        self._sample_rate = sample_rate
        try:
            import sherpa_onnx
        except ImportError as exc:
            raise FatalError("sherpa_onnx is required for SenseVoiceSTT") from exc
        self._recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model_path),
            tokens=str(tokens_path),
            num_threads=num_threads,
            language=language,
            use_itn=use_itn,
            debug=False,
        )
        logger.info("SenseVoice loaded: %s", model_path)

    def _transcribe_sync(self, pcm: bytes) -> str:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        stream = self._recognizer.create_stream()
        stream.accept_waveform(self._sample_rate, audio)
        self._recognizer.decode_stream(stream)
        text = (getattr(stream.result, "text", None) or "").strip()
        # SenseVoice may prepend tags like <|zh|><|HAPPY|><|Speech|>; strip them.
        if text.startswith("<"):
            import re

            text = re.sub(r"^(<\|[^>]+\|>)+", "", text).strip()
        return text

    async def transcribe(self, pcm: bytes) -> str:
        if not pcm:
            raise TransientError("empty pcm")
        try:
            text = await asyncio.to_thread(self._transcribe_sync, pcm)
        except TransientError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"SenseVoice transcribe failed: {exc}") from exc
        if not text:
            raise TransientError("empty transcript")
        logger.info("sensevoice_ms=%s text=%s", "?", text)
        return text
