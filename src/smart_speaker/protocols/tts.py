from typing import Protocol


class TTS(Protocol):
    async def synthesize(self, text: str) -> bytes: ...
