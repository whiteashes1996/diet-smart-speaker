"""Conversation session buffer."""

from __future__ import annotations

from typing import Any

MAX_MESSAGES = 8
MAX_TOOL_RESULT_CHARS = 2000


def truncate_tool_result(text: str, limit: int = MAX_TOOL_RESULT_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"


class Session:
    def __init__(self, max_messages: int = MAX_MESSAGES) -> None:
        self._max = max_messages
        self.messages: list[dict[str, Any]] = []

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})
        self._trim()

    def add_assistant(self, text: str) -> None:
        self.messages.append({"role": "assistant", "content": text})
        self._trim()

    def add_tool_result(self, tool_call_id: str, name: str, content: str) -> None:
        # Kept for tests; next-turn LLM history must not include bare tool messages.
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": truncate_tool_result(content),
            }
        )
        self._trim()

    def history_for_llm(self) -> list[dict[str, Any]]:
        """User/assistant text only. Bare tool rows make DeepSeek return 400."""
        out: list[dict[str, Any]] = []
        for message in self.messages:
            role = message.get("role")
            content = message.get("content")
            if role in ("user", "assistant") and isinstance(content, str) and content:
                out.append({"role": role, "content": content})
        return out

    def _trim(self) -> None:
        # Keep last N user/assistant turns loosely by capping list length
        while len(self.messages) > self._max:
            self.messages.pop(0)
