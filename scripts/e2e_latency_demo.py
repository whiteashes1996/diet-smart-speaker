#!/usr/bin/env python3
"""End-to-end smart-speaker latency demo on Pi.

Pipeline: audio WAV -> whisper.cpp STT -> DeepSeek chat -> Piper TTS
Prints per-stage and total wall times.

Usage:
  export DEEPSEEK_API_KEY=...
  python3 e2e_latency_demo.py --lang zh
  python3 e2e_latency_demo.py --lang en --audio /path/to.wav
  python3 e2e_latency_demo.py --lang zh --play   # play reply if aplay works
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import wave
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path.home() / "voice-bench"
PIPER = ROOT / "tts" / "piper" / "piper"
PIPER_MODELS = {
    "en": ROOT / "tts" / "models" / "en_US-lessac-medium.onnx",
    "zh": ROOT / "tts" / "models" / "zh_CN-huayan-medium.onnx",
}
WHISPER_CLI = ROOT / "whisper.cpp" / "build" / "bin" / "whisper-cli"
WHISPER_MODEL = ROOT / "whisper.cpp" / "models" / "ggml-tiny.bin"
SAMPLES = ROOT / "samples"
OUTDIR = ROOT / "results" / "e2e"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def run(cmd: list[str], *, input_text: str | None = None, env=None, timeout=300) -> tuple[float, str, str, int]:
    t0 = time.perf_counter()
    p = subprocess.run(
        cmd,
        input=input_text,
        text=True if input_text is not None else False,
        capture_output=True,
        env=env,
        timeout=timeout,
    )
    dt = time.perf_counter() - t0
    out = p.stdout if isinstance(p.stdout, str) else (p.stdout or b"").decode("utf-8", "replace")
    err = p.stderr if isinstance(p.stderr, str) else (p.stderr or b"").decode("utf-8", "replace")
    return dt, out, err, p.returncode


def stt_whisper(audio: Path, lang: str, threads: int, model: Path) -> tuple[str, float]:
    cmd = [
        str(WHISPER_CLI),
        "-m", str(model),
        "-f", str(audio),
        "-l", lang,
        "-t", str(threads),
        "-np",
        "-nt",
    ]
    dt, out, err, rc = run(cmd)
    if rc != 0:
        raise RuntimeError(f"whisper failed rc={rc}: {err[-400:]}")
    text = out.strip()
    # whisper-cli with -nt prints plain text; sometimes trailing noise
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # drop ffmpeg/log lines if any leaked
    lines = [ln for ln in lines if not ln.startswith("read_audio") and not ln.startswith("whisper_")]
    text = " ".join(lines).strip()
    if not text:
        # fallback: parse stderr? unlikely
        raise RuntimeError(f"empty STT result. out={out!r} err={err[-200:]!r}")
    return text, dt


def llm_deepseek(user_text: str, lang: str, api_key: str) -> tuple[str, float]:
    system = (
        "You are a concise voice assistant for a smart speaker. "
        "Reply in the same language as the user. Keep answers under 2 short sentences."
        if lang == "en"
        else "你是智能音箱语音助手。用中文简短回答，最多两句，适合朗读。"
    )
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.7,
        "max_tokens": 120,
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"DeepSeek HTTP {e.code}: {detail[:400]}") from e
    dt = time.perf_counter() - t0
    text = (payload["choices"][0]["message"]["content"] or "").strip()
    if not text:
        raise RuntimeError(f"empty DeepSeek response: {payload}")
    return text, dt


def tts_piper(text: str, lang: str, out_wav: Path) -> tuple[float, float]:
    model = PIPER_MODELS[lang]
    env = os.environ.copy()
    lib = str(PIPER.parent)
    env["LD_LIBRARY_PATH"] = lib + ((":" + env["LD_LIBRARY_PATH"]) if env.get("LD_LIBRARY_PATH") else "")
    dt, _o, err, rc = run([str(PIPER), "-m", str(model), "-f", str(out_wav), "-q"], input_text=text, env=env)
    if rc != 0 or not out_wav.exists():
        raise RuntimeError(f"piper failed: {err[-400:]}")
    return dt, wav_duration(out_wav)


def main() -> int:
    ap = argparse.ArgumentParser(description="E2E latency demo: STT -> DeepSeek -> TTS")
    ap.add_argument("--lang", choices=["en", "zh"], default="zh")
    ap.add_argument("--audio", type=Path, default=None, help="Input wav; default uses voice-bench sample")
    ap.add_argument("--whisper-model", type=Path, default=WHISPER_MODEL)
    ap.add_argument("--threads", type=int, default=max(1, os.cpu_count() or 4))
    ap.add_argument("--play", action="store_true", help="Play TTS output with aplay if available")
    ap.add_argument("--rounds", type=int, default=1, help="Repeat full pipeline N times (reports each)")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY", file=sys.stderr)
        return 2

    whisper_model = args.whisper_model

    audio = args.audio or (SAMPLES / f"asr_src_{args.lang}.wav")
    if not audio.exists():
        print(f"ERROR: missing audio {audio}", file=sys.stderr)
        return 2

    OUTDIR.mkdir(parents=True, exist_ok=True)
    audio_s = wav_duration(audio)

    print("== E2E latency demo ==")
    print(f"board: Raspberry Pi")
    print(f"lang={args.lang}  audio={audio}  duration={audio_s:.2f}s")
    print(f"STT=whisper.cpp/{whisper_model.name}  LLM=deepseek-chat  TTS=piper")
    print()

    all_rows = []
    for i in range(1, args.rounds + 1):
        print(f"--- round {i}/{args.rounds} ---")
        t_pipeline = time.perf_counter()

        user_text, stt_s = stt_whisper(audio, args.lang, args.threads, whisper_model)
        print(f"[1] STT   {stt_s:7.3f}s   <- {user_text}")

        reply, llm_s = llm_deepseek(user_text, args.lang, api_key)
        print(f"[2] LLM   {llm_s:7.3f}s   -> {reply}")

        out_wav = OUTDIR / f"reply_{args.lang}_r{i}.wav"
        tts_s, reply_audio_s = tts_piper(reply, args.lang, out_wav)
        print(f"[3] TTS   {tts_s:7.3f}s   audio={reply_audio_s:.2f}s  file={out_wav}")

        total = time.perf_counter() - t_pipeline
        # "time to first audible" ≈ STT+LLM+TTS (before playback)
        print(f"[Σ] TOTAL {total:7.3f}s   (STT+LLM+TTS before play)")
        print(f"    breakdown: STT={stt_s/total*100:.0f}%  LLM={llm_s/total*100:.0f}%  TTS={tts_s/total*100:.0f}%")
        if args.play:
            # playback wall time is audio duration; measure start only
            t0 = time.perf_counter()
            subprocess.run(["aplay", "-q", str(out_wav)], check=False)
            play_s = time.perf_counter() - t0
            print(f"[4] PLAY  {play_s:7.3f}s")
            print(f"[Σ] E2E with play {total + play_s:7.3f}s")
        print()

        row = {
            "round": i,
            "lang": args.lang,
            "input_audio_s": audio_s,
            "stt_s": stt_s,
            "llm_s": llm_s,
            "tts_s": tts_s,
            "reply_audio_s": reply_audio_s,
            "total_before_play_s": total,
            "user_text": user_text,
            "reply_text": reply,
            "out_wav": str(out_wav),
        }
        all_rows.append(row)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_json = OUTDIR / f"e2e_{args.lang}_{stamp}.json"
    out_json.write_text(json.dumps({"runs": all_rows}, ensure_ascii=False, indent=2))
    print(f"saved {out_json}")

    if len(all_rows) > 1:
        def avg(k):
            return sum(r[k] for r in all_rows) / len(all_rows)
        print("== average ==")
        print(f"STT {avg('stt_s'):.3f}s  LLM {avg('llm_s'):.3f}s  TTS {avg('tts_s'):.3f}s  TOTAL {avg('total_before_play_s'):.3f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
