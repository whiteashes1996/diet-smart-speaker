#!/usr/bin/env python3
"""Pi wake test: TTS prompt → record ~5s → openWakeWord → TTS result.

Usage on Raspberry Pi:
  PYTHONPATH=src python scripts/pi_wake_record_test.py
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

from smart_speaker.adapters.wake.openwakeword_wake import OpenWakeWordWake

SAMPLE_RATE = 16000
RECORD_S = 5.0
OWW_FRAME = 1280  # 80 ms @ 16 kHz

PIPER_BIN = Path.home() / "voice-bench/tts/piper/piper"
PIPER_MODEL = Path.home() / "voice-bench/tts/models/zh_CN-huayan-medium.onnx"


def speak(text: str, *, play: bool = True) -> Path:
    if not PIPER_BIN.is_file():
        raise FileNotFoundError(f"Piper not found: {PIPER_BIN}")
    if not PIPER_MODEL.is_file():
        raise FileNotFoundError(f"Piper model not found: {PIPER_MODEL}")

    out = Path(tempfile.mkstemp(prefix="pi-wake-tts-", suffix=".wav")[1])
    proc = subprocess.run(
        [str(PIPER_BIN), "--model", str(PIPER_MODEL), "--output_file", str(out)],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"piper failed: {proc.stderr[-400:]}")
    if play:
        # Prefer USB speaker if present; fall back to default.
        rc = subprocess.run(
            ["aplay", "-q", "-D", "plughw:2,0", str(out)],
            capture_output=True,
        ).returncode
        if rc != 0:
            subprocess.run(["aplay", "-q", str(out)], check=False)
    return out


def record_pcm(seconds: float, device: str) -> bytes:
    """Record mono s16le @ 16 kHz via arecord."""
    n_samples = int(seconds * SAMPLE_RATE)
    cmd = [
        "arecord",
        "-q",
        "-D",
        device,
        "-f",
        "S16_LE",
        "-c",
        "1",
        "-r",
        str(SAMPLE_RATE),
        "-d",
        str(max(1, int(round(seconds)))),
        "-t",
        "raw",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"arecord failed rc={proc.returncode}: {(proc.stderr or b'').decode()[-400:]}"
        )
    pcm = proc.stdout
    # Trim/pad to expected length for deterministic frames.
    want = n_samples * 2
    if len(pcm) < want:
        pcm = pcm + b"\x00" * (want - len(pcm))
    return pcm[:want]


def save_wav(path: Path, pcm: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)


def detect_wake(pcm: bytes, model_name: str, threshold: float) -> tuple[bool, float]:
    wake = OpenWakeWordWake(model_name=model_name, threshold=threshold)
    best = 0.0
    hit = False
    # Feed fixed 80 ms frames.
    for i in range(0, len(pcm) - OWW_FRAME * 2 + 1, OWW_FRAME * 2):
        chunk = pcm[i : i + OWW_FRAME * 2]
        if wake.process_chunk(chunk):
            hit = True
            best = max(best, wake.last_score)
            break
        best = max(best, wake.last_score)
    return hit, best


def main() -> int:
    parser = argparse.ArgumentParser(description="Pi wake record test")
    parser.add_argument("--seconds", type=float, default=RECORD_S)
    parser.add_argument(
        "--device",
        default="plughw:2,0",
        help="ALSA capture device (default USB Audio plughw:2,0)",
    )
    parser.add_argument("--model", default="hey_jarvis")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--save", type=Path, default=Path("/tmp/pi-wake-record.wav"))
    args = parser.parse_args()

    print("1) 播放提示音…", flush=True)
    speak("准备开始录音了，请说嘿贾维斯")

    print(f"2) 录音 {args.seconds:.1f}s（设备 {args.device}）…", flush=True)
    pcm = record_pcm(args.seconds, args.device)
    save_wav(args.save, pcm)
    peak = float(np.max(np.abs(np.frombuffer(pcm, dtype=np.int16)))) if pcm else 0.0
    print(f"   已保存 {args.save}，峰值={peak:.0f}", flush=True)

    print("3) 检测唤醒…", flush=True)
    hit, score = detect_wake(pcm, args.model, args.threshold)
    print(f"   model={args.model} threshold={args.threshold} best_score={score:.3f}", flush=True)

    if hit:
        print("WAKE_OK", flush=True)
        speak("唤醒成功")
        return 0

    print("WAKE_MISS", flush=True)
    speak("没有检测到唤醒")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — surface clearly on Pi SSH
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
