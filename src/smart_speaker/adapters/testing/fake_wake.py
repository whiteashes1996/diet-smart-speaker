"""Fake WakeWord — triggers after N chunks for unit tests."""

from __future__ import annotations


class FakeWakeWord:
    """In-memory WakeWord that triggers after a fixed number of chunks."""

    def __init__(self, trigger_after_chunks: int = 3) -> None:
        self._trigger_after = trigger_after_chunks
        self._count = 0

    def process_chunk(self, pcm: bytes) -> bool:
        self._count += 1
        return self._count >= self._trigger_after
