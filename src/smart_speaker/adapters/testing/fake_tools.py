"""Fake ToolBackend."""

from __future__ import annotations

import json
from typing import Any

from smart_speaker.protocols.tools import ToolSpec


class FakeTools:
    def __init__(
        self,
        tools: list[ToolSpec] | None = None,
        fail_call: bool = False,
    ) -> None:
        self._tools = tools or [
            ToolSpec(name="log_food", description="log", parameters={}),
            ToolSpec(name="get_daily_summary", description="summary", parameters={}),
            ToolSpec(name="add_task", description="should be filtered", parameters={}),
        ]
        self.fail_call = fail_call
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        self.calls.append((name, arguments))
        if self.fail_call:
            raise RuntimeError("mcp down")
        return json.dumps({"ok": True, "tool": name, "args": arguments})
