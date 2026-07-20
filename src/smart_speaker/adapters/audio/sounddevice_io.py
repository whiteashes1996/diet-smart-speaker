"""SoundDevice-backed AudioIO implementation."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from smart_speaker.config import AppConfig

CHUNK_BYTES = 1280
CHUNK_SAMPLES = CHUNK_BYTES // 2


class SoundDeviceAudioIO:
    """Capture and playback via sounddevice (pcm_s16le mono)."""

    def __init__(self, config: AppConfig) -> None:
        self._sample_rate = config.sample_rate
        self._callback: Callable[[bytes], None] | None = None
        self._capture_enabled = True
        self._stream: sd.RawInputStream | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start_input(self, callback: Callable[[bytes], None]) -> None:
        with self._lock:
            self._callback = callback
            self._capture_enabled = True
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._stream = sd.RawInputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
            )
            self._stream.start()
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            stream = self._stream
            if stream is None:
                break
            data, _overflowed = stream.read(CHUNK_SAMPLES)
            if self._stop_event.is_set():
                break
            with self._lock:
                if not self._capture_enabled or self._callback is None:
                    continue
                cb = self._callback
            cb(bytes(data))

    def stop_input(self) -> None:
        self._stop_event.set()
        with self._lock:
            self._callback = None
            stream = self._stream
            thread = self._thread
            self._stream = None
            self._thread = None

        if stream is not None:
            stream.stop()
            stream.close()
        if thread is not None:
            thread.join(timeout=2.0)

    def play(self, pcm: bytes) -> None:
        samples = np.frombuffer(pcm, dtype=np.int16)
        sd.play(samples, samplerate=self._sample_rate)
        sd.wait()

    def set_capture_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._capture_enabled = enabled
