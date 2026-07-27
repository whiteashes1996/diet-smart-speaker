"""Fake TTS — returns fixed pcm."""

from __future__ import annotations

from smart_speaker.errors import TransientError


class FakeTTS:
    def __init__(self, pcm: bytes = b"\x00\x01" * 800) -> None:
        self.pcm = pcm
        self.texts: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            raise TransientError("empty TTS text")
        self.texts.append(text)
        return self.pcm
