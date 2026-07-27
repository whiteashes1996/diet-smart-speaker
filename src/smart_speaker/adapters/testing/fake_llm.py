"""Fake LLM for orchestrator tests."""

from __future__ import annotations

from typing import Any

from smart_speaker.protocols.llm import LLMResult, ToolCall


class FakeLLM:
    def __init__(self, results: list[LLMResult] | None = None) -> None:
        self._results = list(
            results
            or [LLMResult(final_text="好的，已记录两个鸡蛋。")]
        )
        self.calls = 0
        self.messages_log: list[list[dict[str, Any]]] = []

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        self.calls += 1
        self.messages_log.append(messages)
        if not self._results:
            return LLMResult(final_text="（无更多回复）")
        return self._results.pop(0)


def tool_then_text(
    tool_name: str = "log_food",
    arguments: dict[str, Any] | None = None,
    final: str = "已记好。",
) -> list[LLMResult]:
    return [
        LLMResult(
            tool_calls=[ToolCall(id="1", name=tool_name, arguments=arguments or {"name": "鸡蛋"})]
        ),
        LLMResult(final_text=final),
    ]
