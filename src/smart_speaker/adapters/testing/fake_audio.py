from __future__ import annotations

from collections.abc import Callable


class FakeAudioIO:
    """In-memory AudioIO for unit tests."""

    def __init__(self) -> None:
        self.played: list[bytes] = []
        self._callback: Callable[[bytes], None] | None = None
        self._capture_enabled = True

    def start_input(self, callback: Callable[[bytes], None]) -> None:
        self._callback = callback
        self._capture_enabled = True

    def stop_input(self) -> None:
        self._callback = None

    def play(self, pcm: bytes) -> None:
        self.played.append(pcm)

    def set_capture_enabled(self, enabled: bool) -> None:
        self._capture_enabled = enabled

    def inject_chunk(self, chunk: bytes) -> None:
        if self._callback is not None and self._capture_enabled:
            self._callback(chunk)
