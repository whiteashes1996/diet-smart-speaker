from typing import Protocol


class WakeWord(Protocol):
    def process_chunk(self, pcm: bytes) -> bool: ...
