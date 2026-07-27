"""Fake STT for unit and orchestrator tests."""

from __future__ import annotations

from smart_speaker.errors import TransientError


class FakeSTT:
    def __init__(self, text: str = "今天中午吃了鸡蛋", fail: bool = False) -> None:
        self.text = text
        self.fail = fail
        self.last_pcm: bytes | None = None
        self.calls = 0

    async def transcribe(self, pcm: bytes) -> str:
        self.calls += 1
        self.last_pcm = pcm
        if self.fail:
            raise TransientError("empty transcript")
        return self.text

    @property
    def last_input_or_text(self) -> str:
        return self.text
