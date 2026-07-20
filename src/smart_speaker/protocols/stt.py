from typing import Protocol


class STT(Protocol):
    async def transcribe(self, pcm: bytes) -> str: ...
