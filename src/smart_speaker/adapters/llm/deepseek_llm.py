"""DeepSeek LLM via OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from smart_speaker.errors import TransientError
from smart_speaker.protocols.llm import LLMResult, ToolCall

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


class DeepSeekLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    async def _create(self, **kwargs: Any) -> Any:
        return await self._client.chat.completions.create(**kwargs)

    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        try:
            resp = await self._create(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"LLM request failed: {exc}") from exc
        choice = resp.choices[0].message
        tool_calls: list[ToolCall] = []
        for tc in choice.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(id=tc.id, name=tc.function.name, arguments=args if isinstance(args, dict) else {})
            )
        if tool_calls:
            return LLMResult(tool_calls=tool_calls)
        text = (choice.content or "").strip()
        if not text:
            raise TransientError("empty LLM response")
        return LLMResult(final_text=text)
