"""edge-tts adapter → pcm_s16le 16k mono."""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

import edge_tts
import numpy as np

from smart_speaker.errors import FatalError, TransientError

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


class EdgeTTSAdapter:
    def __init__(self, voice: str = DEFAULT_VOICE, sample_rate: int = 16000) -> None:
        self._voice = voice
        self._sample_rate = sample_rate

    async def _fetch_mp3(self, text: str) -> bytes:
        communicate = edge_tts.Communicate(text, self._voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def _mp3_to_pcm(self, mp3: bytes) -> bytes:
        try:
            from pydub import AudioSegment
        except ImportError as exc:
            raise FatalError(
                "pydub is required for EdgeTTS pcm decode; pip install pydub and install ffmpeg"
            ) from exc
        try:
            segment = AudioSegment.from_file(io.BytesIO(mp3), format="mp3")
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"mp3 decode failed (is ffmpeg installed?): {exc}") from exc
        segment = segment.set_frame_rate(self._sample_rate).set_channels(1).set_sample_width(2)
        return segment.raw_data

    async def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            raise TransientError("empty TTS text")
        mp3 = await self._fetch_mp3(text)
        if not mp3:
            raise TransientError("empty TTS audio")
        pcm = self._mp3_to_pcm(mp3)
        logger.info("tts_pcm_bytes=%s", len(pcm))
        return pcm

    async def synthesize_mp3_file(self, text: str, path: Path | None = None) -> Path:
        """Write mp3 for manual listening (afplay) without ffmpeg."""
        import os

        mp3 = await self._fetch_mp3(text)
        if path is None:
            fd, name = tempfile.mkstemp(suffix=".mp3")
            os.close(fd)
            path = Path(name)
        path.write_bytes(mp3)
        return path
