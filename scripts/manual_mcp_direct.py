#!/usr/bin/env python3
"""Direct Health MCP smoke (no LLM, no mic)."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_speaker.adapters.tools.mcp_health import (  # noqa: E402
    DIET_TOOL_WHITELIST,
    build_mcp_health_backend,
)
from smart_speaker.config import load_config  # noqa: E402


def _ok(name: str, detail: str) -> None:
    print(f"PASS {name}: {detail[:240]}")


def _fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail[:400]}")


async def _run() -> int:
    cfg = load_config()
    backend = build_mcp_health_backend(cfg)
    if backend is None:
        print("FAIL connect: MCP_HEALTH_URL or MCP_HEALTH_COMMAND missing", file=sys.stderr)
        return 1
    await backend.connect()
    failed = 0
    try:
        tools = await backend.refresh_tools()
        names = {t.name for t in tools}
        expected = {"log_food", "get_day", "get_daily_summary", "get_goals"}
        missing = expected - names
        if missing:
            _fail("list_tools", f"missing {sorted(missing)}; got {sorted(names)}")
            failed += 1
        else:
            _ok("list_tools", ",".join(sorted(names)))

        today = datetime.now(ZoneInfo(cfg.timezone)).date().isoformat()

        log_out = await backend.call(
            "log_food",
            {"name": "鸡蛋", "pieces": 2, "meal": "午", "date": today},
        )
        if "error" in log_out.lower() and "ok" not in log_out.lower():
            _fail("log_food", log_out)
            failed += 1
        else:
            _ok("log_food", log_out)

        day = await backend.call("get_day", {"date": today})
        if "鸡蛋" not in day:
            _fail("get_day", f"鸡蛋 not in {day[:300]}")
            failed += 1
        else:
            _ok("get_day", "found 鸡蛋")

        for tool, args in (
            ("get_daily_summary", {"date": today}),
            ("get_goals", {}),
            ("get_trend", {"start": today, "end": today}),
            ("list_foods", {}),
        ):
            if tool not in names:
                _ok(tool, "not advertised, skipped")
                continue
            out = await backend.call(tool, args)
            if out.startswith('{"error"'):
                _fail(tool, out)
                failed += 1
            else:
                _ok(tool, out)

        denied = await backend.call("not_a_real_tool", {})
        if "not allowed" in denied or "error" in denied:
            _ok("whitelist_deny", denied)
        else:
            _fail("whitelist_deny", denied)
            failed += 1

        print(f"whitelist={sorted(DIET_TOOL_WHITELIST)}")
        return 1 if failed else 0
    finally:
        await backend.close()


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
