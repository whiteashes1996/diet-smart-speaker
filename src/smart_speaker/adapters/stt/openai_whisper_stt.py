"""OpenAI-compatible Whisper STT adapter."""

from __future__ import annotations

import io
import logging
import time
import wave
from typing import Any

from openai import AsyncOpenAI

from smart_speaker.errors import TransientError

logger = logging.getLogger(__name__)


def pcm_s16le_to_wav_bytes(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class OpenAIWhisperSTT:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
        sample_rate: int = 16000,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._sample_rate = sample_rate

    async def _transcribe_file(self, **kwargs: Any) -> Any:
        return await self._client.audio.transcriptions.create(**kwargs)

    async def transcribe(self, pcm: bytes) -> str:
        wav = pcm_s16le_to_wav_bytes(pcm, self._sample_rate)
        started = time.perf_counter()
        try:
            result = await self._transcribe_file(
                model=self._model,
                file=("audio.wav", wav, "audio/wav"),
            )
        except Exception as exc:  # noqa: BLE001 — map to transient for caller
            raise TransientError(f"STT request failed: {exc}") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info("stt_ms=%s", elapsed_ms)
        text = (getattr(result, "text", None) or "").strip()
        if not text:
            raise TransientError("empty transcript")
        return text
