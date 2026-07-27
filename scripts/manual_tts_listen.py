#!/usr/bin/env python3
"""Play TTS via edge-tts + afplay (mp3), no ffmpeg required for listen."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_speaker.adapters.tts.edge_tts_tts import EdgeTTSAdapter


async def _run(text: str) -> int:
    tts = EdgeTTSAdapter()
    path = await tts.synthesize_mp3_file(text)
    print(f"Wrote {path}")
    subprocess.run(["afplay", str(path)], check=False)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--text", default="已记录两个鸡蛋")
    args = p.parse_args()
    return asyncio.run(_run(args.text))


if __name__ == "__main__":
    raise SystemExit(main())
