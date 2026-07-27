"""MCP stdio ToolBackend with diet tool whitelist."""

from __future__ import annotations

import json
import logging
from typing import Any

from smart_speaker.errors import FatalError, TransientError
from smart_speaker.protocols.tools import ToolSpec

logger = logging.getLogger(__name__)

DIET_TOOL_WHITELIST = frozenset(
    {
        "log_food",
        "list_foods",
        "add_food",
        "get_day",
        "get_daily_summary",
        "get_goals",
        "get_trend",
        "update_entry",
        "delete_entry",
    }
)


class McpHealthToolBackend:
    """Spawn health MCP via stdio and expose whitelisted tools only."""

    def __init__(self, command: str) -> None:
        if not command or not command.strip():
            raise FatalError("MCP_HEALTH_COMMAND is required")
        self._command = command.strip()
        self._session: Any = None
        self._cm: Any = None
        self._tools_cache: list[ToolSpec] | None = None

    async def connect(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # shell-style: first token is executable, rest args
        parts = self._command.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:], env=None)
        self._cm = stdio_client(params)
        read, write = await self._cm.__aenter__()
        self._session = ClientSession(read, write)
        await self._session.__aenter__()
        await self._session.initialize()
        logger.info("mcp health connected: %s", parts[0])

    async def close(self) -> None:
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._cm is not None:
            await self._cm.__aexit__(None, None, None)
            self._cm = None

    def list_tools(self) -> list[ToolSpec]:
        if self._tools_cache is None:
            raise FatalError("MCP tools not loaded; call refresh_tools() first")
        return list(self._tools_cache)

    async def refresh_tools(self) -> list[ToolSpec]:
        if self._session is None:
            raise FatalError("MCP not connected")
        result = await self._session.list_tools()
        specs: list[ToolSpec] = []
        for tool in result.tools:
            if tool.name not in DIET_TOOL_WHITELIST:
                continue
            schema = tool.inputSchema if isinstance(tool.inputSchema, dict) else {}
            specs.append(
                ToolSpec(
                    name=tool.name,
                    description=tool.description or "",
                    parameters=schema,
                )
            )
        self._tools_cache = specs
        return specs

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in DIET_TOOL_WHITELIST:
            return json.dumps({"error": f"tool not allowed: {name}"})
        if self._session is None:
            return json.dumps({"error": "MCP not connected"})
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:  # noqa: BLE001
            raise TransientError(f"MCP call failed: {exc}") from exc
        parts: list[str] = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
            else:
                parts.append(str(block))
        out = "\n".join(parts) if parts else json.dumps({"ok": True})
        if len(out) > 2000:
            out = out[:2000] + "…"
        return out


class FilteringToolBackend:
    """Wrap any backend and filter list_tools by whitelist (for tests)."""

    def __init__(self, inner: Any, whitelist: frozenset[str] = DIET_TOOL_WHITELIST) -> None:
        self._inner = inner
        self._whitelist = whitelist

    def list_tools(self) -> list[ToolSpec]:
        return [t for t in self._inner.list_tools() if t.name in self._whitelist]

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        if name not in self._whitelist:
            return json.dumps({"error": f"tool not allowed: {name}"})
        return await self._inner.call(name, arguments)
