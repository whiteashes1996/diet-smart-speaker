"""SoundDevice-backed AudioIO implementation."""

from __future__ import annotations

import threading
from collections.abc import Callable

import numpy as np
import sounddevice as sd

from smart_speaker.config import AppConfig

# openWakeWord pretrained models expect 80 ms frames @ 16 kHz = 1280 samples
CHUNK_SAMPLES = 1280
CHUNK_BYTES = CHUNK_SAMPLES * 2


def resolve_input_device(preferred: str | None = None) -> int | None:
    """Pick an input device index. Prefer MacBook mic; avoid Teams/virtual."""
    devices = sd.query_devices()
    preferred_l = (preferred or "").lower().strip()
    mac_idx = None
    fallback = None
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        name = str(d["name"])
        lower = name.lower()
        if preferred_l and preferred_l in lower:
            return i
        if "teams" in lower or "zoom" in lower or "cable" in lower:
            continue
        if "macbook" in lower and "mic" in lower:
            mac_idx = i
        if fallback is None and "iphone" not in lower:
            fallback = i
    if mac_idx is not None:
        return mac_idx
    return fallback if fallback is not None else sd.default.device[0]


class SoundDeviceAudioIO:
    """Capture and playback via sounddevice (pcm_s16le mono)."""

    def __init__(
        self,
        config: AppConfig,
        input_device: int | None = None,
        output_device: int | None = None,
        playback_rate: int | None = None,
    ) -> None:
        self._sample_rate = config.sample_rate
        self._input_device = (
            input_device
            if input_device is not None
            else resolve_input_device(getattr(config, "audio_input_device", None))
        )
        self._output_device = output_device
        # Playback sample rate; if the chosen output device cannot open it
        # (e.g. USB speaker at 16 kHz), we resample on the fly to its rate.
        self._playback_rate = playback_rate or config.sample_rate
        self._callback: Callable[[bytes], None] | None = None
        self._capture_enabled = True
        self._stream: sd.RawInputStream | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._capture_rate = self._resolve_capture_rate()

    def _resolve_capture_rate(self) -> int:
        """Pick an input sample rate the mic can open (USB mics often need 48k)."""
        for rate in (self._sample_rate, 48000, 44100, 16000):
            try:
                sd.check_input_settings(
                    device=self._input_device, channels=1, dtype="int16", samplerate=rate
                )
                return rate
            except Exception:  # noqa: BLE001
                continue
        return self._sample_rate

    def _resolve_output(self) -> tuple[int | None, int]:
        """Pick output device and a sample rate it can actually open."""
        device = self._output_device
        candidates = [self._playback_rate, 48000, 44100]
        for rate in candidates:
            try:
                sd.check_output_settings(
                    device=device, channels=1, dtype="int16", samplerate=rate
                )
                return device, rate
            except Exception:  # noqa: BLE001
                continue
        # Last resort: let PortAudio pick.
        return device, self._sample_rate

    def start_input(self, callback: Callable[[bytes], None]) -> None:
        with self._lock:
            self._callback = callback
            self._capture_enabled = True
            if self._thread is not None and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._stream = sd.RawInputStream(
                samplerate=self._capture_rate,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
                device=self._input_device,
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
            pcm = self._downsample_input(bytes(data))
            with self._lock:
                if not self._capture_enabled or self._callback is None:
                    continue
                cb = self._callback
            cb(pcm)

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

    def _resample(self, samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
        if src_rate == dst_rate or samples.size < 2:
            return samples
        n_out = int(round(samples.shape[0] * dst_rate / float(src_rate)))
        if n_out < 1:
            return samples
        x = np.arange(samples.shape[0], dtype=np.float64)
        xq = np.linspace(0.0, float(samples.shape[0] - 1), n_out)
        return np.interp(xq, x, samples.astype(np.float64)).round().astype(np.int16)

    def _downsample_input(self, pcm: bytes) -> bytes:
        """Mic may capture at a higher rate than the pipeline expects."""
        if self._capture_rate == self._sample_rate:
            return pcm
        samples = np.frombuffer(pcm, dtype=np.int16)
        return self._resample(samples, self._capture_rate, self._sample_rate).tobytes()

    def play(self, pcm: bytes) -> None:
        samples = np.frombuffer(pcm, dtype=np.int16)
        device, rate = self._resolve_output()
        if rate != self._sample_rate:
            samples = self._resample(samples, self._sample_rate, rate)
        sd.play(samples, samplerate=rate, device=device)
        sd.wait()

    def set_capture_enabled(self, enabled: bool) -> None:
        with self._lock:
            self._capture_enabled = enabled
