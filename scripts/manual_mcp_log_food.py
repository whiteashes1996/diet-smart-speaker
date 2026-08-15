#!/usr/bin/env python3
"""Text-only MCP diet smoke: log_food then get_day."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_speaker.adapters.tools.mcp_health import build_mcp_health_backend
from smart_speaker.config import load_config


async def _run(name: str, pieces: float, meal: str) -> int:
    cfg = load_config()
    backend = build_mcp_health_backend(cfg)
    if backend is None:
        print("MCP_HEALTH_URL or MCP_HEALTH_COMMAND missing", file=sys.stderr)
        return 1
    await backend.connect()
    try:
        await backend.refresh_tools()
        today = datetime.now(ZoneInfo(cfg.timezone)).date().isoformat()
        out = await backend.call(
            "log_food",
            {"name": name, "pieces": pieces, "meal": meal, "date": today},
        )
        print("log_food:", out)
        day = await backend.call("get_day", {"date": today})
        print("get_day:", day[:2000])
        return 0
    finally:
        await backend.close()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--name", default="鸡蛋")
    p.add_argument("--pieces", type=float, default=2)
    p.add_argument("--meal", default="午")
    args = p.parse_args()
    return asyncio.run(_run(args.name, args.pieces, args.meal))


if __name__ == "__main__":
    raise SystemExit(main())
