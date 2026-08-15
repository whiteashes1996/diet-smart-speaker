"""Diagnose why hey_jarvis score stays ~0 on clear audio."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import openwakeword
from openwakeword.model import Model

SR = 16000
FRAME = 1280
ONNX = Path(openwakeword.__file__).parent / "resources/models/hey_jarvis_v0.1.onnx"


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        rate = wf.getframerate()
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        audio = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        print(f"  file={path.name} rate={rate} ch={ch} sw={sw} n={len(audio)} peak={int(np.max(np.abs(audio)))}")
        if ch != 1:
            audio = audio.reshape(-1, ch)[:, 0]
        if rate != SR:
            x = np.linspace(0, 1, len(audio))
            n = int(len(audio) * SR / rate)
            audio = np.interp(np.linspace(0, 1, n), x, audio.astype(np.float32)).astype(np.int16)
            print(f"  resampled -> {len(audio)} samples @ {SR}")
    return audio


def max_score(audio: np.ndarray, label: str) -> float:
    m = Model(wakeword_models=[str(ONNX)], inference_framework="onnx")
    best = 0.0
    at = 0
    for i in range(0, max(0, len(audio) - FRAME), FRAME):
        scores = m.predict(audio[i : i + FRAME])
        v = float(max(scores.values()) if scores else 0.0)
        if v > best:
            best = v
            at = i
    print(f"{label}: max_score={best:.6f} at_t={at/SR:.2f}s  pass0.5={best>=0.5}")
    return best


def energy_timeline(audio: np.ndarray, label: str) -> None:
    print(f"{label} energy (peak per 0.5s):")
    step = SR // 2
    for i in range(0, len(audio), step):
        seg = audio[i : i + step]
        if not len(seg):
            break
        p = int(np.max(np.abs(seg)))
        bar = "#" * min(40, p // 200)
        print(f"  {i/SR:5.1f}s  peak={p:5d} |{bar}")


def main() -> None:
    print("ONNX exists", ONNX.is_file(), ONNX)
    import onnxruntime as ort

    print("ort", ort.__version__)
    print("oww", getattr(openwakeword, "__version__", "?"))

    paths = [
        ("USER", Path("/tmp/smart-speaker-record-15s.wav")),
        ("TTS_a", Path("/tmp/oww-ref-a.wav")),
        ("TTS_b", Path("/tmp/oww-ref-b.wav")),
        ("TTS_old", Path("/tmp/oww-ref-hey-jarvis.wav")),
    ]
    scores = {}
    for label, path in paths:
        if not path.is_file():
            print(f"missing {path}")
            continue
        print(f"\n=== {label} ===")
        audio = load_wav(path)
        if label == "USER":
            energy_timeline(audio, label)
        scores[label] = max_score(audio, label)

    print("\n=== CONCLUSION ===")
    user = scores.get("USER", 0)
    tts_best = max((v for k, v in scores.items() if k.startswith("TTS")), default=0)
    print(f"user_max={user:.6f} tts_best={tts_best:.6f}")
    if tts_best >= 0.3 and user < 0.1:
        print("CAUSE: likely accent/pronunciation mismatch (TTS English triggers, yours does not)")
    elif tts_best < 0.1 and user < 0.1:
        print("CAUSE: pipeline/model issue — even standard TTS English fails; NOT just your accent")
    elif user >= 0.3:
        print("CAUSE: model can detect your speech offline — live path bug")
    else:
        print("CAUSE: mixed / unclear — inspect numbers above")


if __name__ == "__main__":
    main()
