#!/usr/bin/env python3
"""Text-only e2e on Pi: text -> DeepSeek -> Health MCP -> reply. No mic/speaker."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from smart_speaker.adapters.llm.deepseek_llm import DeepSeekLLM  # noqa: E402
from smart_speaker.adapters.testing.fake_audio import FakeAudioIO  # noqa: E402
from smart_speaker.adapters.testing.fake_stt import FakeSTT  # noqa: E402
from smart_speaker.adapters.testing.fake_tts import FakeTTS  # noqa: E402
from smart_speaker.adapters.testing.fake_wake import FakeWakeWord  # noqa: E402
from smart_speaker.adapters.tools.local_notes import (  # noqa: E402
    LocalNoteToolBackend,
    MultiToolBackend,
)
from smart_speaker.adapters.tools.mcp_health import build_mcp_health_backend  # noqa: E402
from smart_speaker.config import load_config  # noqa: E402
from smart_speaker.orchestrator.state_machine import Orchestrator  # noqa: E402


class RecordingTools:
    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls: list[tuple[str, dict[str, Any], str]] = []

    def list_tools(self) -> list[Any]:
        return self._inner.list_tools()

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        out = await self._inner.call(name, arguments)
        self.calls.append((name, arguments, out))
        print(f"  TOOL {name}({json.dumps(arguments, ensure_ascii=False)}) -> {out[:240]}")
        return out


def _names(rec: RecordingTools) -> list[str]:
    return [n for n, _a, _o in rec.calls]


async def _build_orch(cfg, rec: RecordingTools) -> Orchestrator:
    return Orchestrator(
        config=cfg,
        audio=FakeAudioIO(),
        wake=FakeWakeWord(),
        stt=FakeSTT(),
        llm=DeepSeekLLM(api_key=cfg.deepseek_api_key),
        tts=FakeTTS(),
        tools=rec,
    )


async def _run_text(cfg, rec: RecordingTools, text: str) -> str:
    rec.calls.clear()
    orch = await _build_orch(cfg, rec)
    print(f"\n=== USER: {text} ===")
    reply = await orch.run_turn_from_pcm(b"", user_text_override=text)
    print(f"REPLY: {reply}")
    print(f"TOOLS: {_names(rec)}")
    return reply


async def _run_short_filter(cfg) -> bool:
    rec = RecordingTools(MultiToolBackend([]))
    orch = Orchestrator(
        config=cfg,
        audio=FakeAudioIO(),
        wake=FakeWakeWord(),
        stt=FakeSTT(text="嗯"),
        llm=DeepSeekLLM(api_key=cfg.deepseek_api_key),
        tts=FakeTTS(),
        tools=rec,
    )
    orch._enter_conversation()
    orch._reset_listen()
    orch._utterance = bytearray(b"\xff\x7f" * 640)
    print("\n=== USER: 嗯 (short-filter via STT) ===")
    await orch._finish_listening()
    skipped = rec.calls == [] and orch.state.value == "listening"
    print(f"TOOLS: {_names(rec)} state={orch.state.value} skip_llm={skipped}")
    return skipped


async def _run() -> int:
    cfg = load_config()
    if not cfg.deepseek_api_key:
        print("FAIL: DEEPSEEK_API_KEY missing", file=sys.stderr)
        return 1
    health = build_mcp_health_backend(cfg)
    if health is None:
        print("FAIL: MCP_HEALTH_URL missing", file=sys.stderr)
        return 1
    await health.connect()
    await health.refresh_tools()
    notes = LocalNoteToolBackend(memory_dir=cfg.memory_dir)
    rec = RecordingTools(MultiToolBackend([health, notes]))
    failed = 0
    try:
        reply = await _run_text(cfg, rec, "记一下今天中午吃了两个鸡蛋")
        if "log_food" not in _names(rec):
            print("FAIL expected log_food")
            failed += 1
        elif not reply.strip():
            print("FAIL empty reply after log_food")
            failed += 1
        else:
            print("PASS log_food via LLM")

        rec2 = RecordingTools(MultiToolBackend([health, notes]))
        reply = await _run_text(cfg, rec2, "我今天还剩多少热量")
        used = set(_names(rec2))
        if not used.intersection({"get_daily_summary", "get_goals", "get_day"}):
            print("FAIL expected summary/goals/day")
            failed += 1
        elif not reply.strip():
            print("FAIL empty remaining-kcal reply")
            failed += 1
        else:
            # goals may be empty on this account; tool call + a reply is enough
            print("PASS remaining kcal via LLM")

        rec3 = RecordingTools(MultiToolBackend([health, notes]))
        reply = await _run_text(cfg, rec3, "我今天吃了什么")
        used = set(_names(rec3))
        if not used.intersection({"get_day", "get_daily_summary"}):
            print("FAIL expected get_day/summary")
            failed += 1
        elif not reply.strip():
            print("FAIL empty reply")
            failed += 1
        else:
            print("PASS today foods via LLM")

        rec4 = RecordingTools(MultiToolBackend([health, notes]))
        reply = await _run_text(cfg, rec4, "你好")
        if not reply.strip():
            print("FAIL hello empty")
            failed += 1
        else:
            print("PASS hello (LLM reachable)")

        if await _run_short_filter(cfg):
            print("PASS short transcript skipped LLM")
        else:
            print("FAIL short transcript was sent to LLM")
            failed += 1

        return 1 if failed else 0
    finally:
        await health.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
