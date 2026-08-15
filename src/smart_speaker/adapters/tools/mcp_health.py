"""Health MCP ToolBackend: streamable-HTTP or stdio, diet tool whitelist."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from smart_speaker.config import AppConfig
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

_MAX_TOOL_RESULT_CHARS = 2000


def _async_http_client_cls() -> Any:
    """MCP 2.x uses httpx2; 1.x uses httpx."""
    try:
        import httpx2

        return httpx2.AsyncClient
    except ImportError:  # pragma: no cover
        import httpx

        return httpx.AsyncClient


def resolve_mcp_health_token(config: AppConfig) -> str | None:
    """Prefer inline token; otherwise read token file (tilde-expanded)."""
    if config.mcp_health_token:
        token = config.mcp_health_token.strip()
        return token or None
    if config.mcp_health_token_file:
        path = Path(config.mcp_health_token_file).expanduser()
        if not path.is_file():
            return None
        token = path.read_text(encoding="utf-8").strip()
        return token or None
    return None


def build_mcp_health_backend(config: AppConfig) -> McpHealthToolBackend | None:
    """URL wins over stdio command. Returns None if neither is configured."""
    url = (config.mcp_health_url or "").strip() or None
    command = (config.mcp_health_command or "").strip() or None
    if url:
        token = resolve_mcp_health_token(config)
        if not token:
            raise FatalError("MCP_HEALTH_TOKEN is required when MCP_HEALTH_URL is set")
        return McpHealthToolBackend(
            url=url,
            token=token,
            ca_file=config.mcp_health_ca_file,
        )
    if command:
        return McpHealthToolBackend(command=command)
    return None


class McpHealthToolBackend:
    """Connect to health MCP via streamable-HTTP or stdio; expose diet tools only."""

    def __init__(
        self,
        command: str | None = None,
        *,
        url: str | None = None,
        token: str | None = None,
        ca_file: str | None = None,
    ) -> None:
        self._url = (url or "").strip() or None
        self._token = (token or "").strip() or None
        self._ca_file = (ca_file or "").strip() or None
        self._command = (command or "").strip() or None
        if not self._url and not self._command:
            raise FatalError("MCP_HEALTH_URL or MCP_HEALTH_COMMAND is required")
        if self._url and not self._token:
            raise FatalError("MCP_HEALTH_TOKEN is required when using MCP_HEALTH_URL")
        self._session: Any = None
        self._cm: Any = None
        self._http_client: Any = None
        self._tools_cache: list[ToolSpec] | None = None

    def _make_http_client(self) -> Any:
        import ssl

        client_cls = _async_http_client_cls()
        timeout: Any
        try:
            import httpx2

            timeout = httpx2.Timeout(30.0, read=300.0)
        except ImportError:  # pragma: no cover
            import httpx

            timeout = httpx.Timeout(30.0, read=300.0)

        verify: ssl.SSLContext | bool = False
        if self._ca_file:
            ca = Path(self._ca_file).expanduser()
            if ca.is_file():
                verify = ssl.create_default_context(cafile=str(ca))
        return client_cls(
            verify=verify,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json, text/event-stream",
            },
            timeout=timeout,
            trust_env=False,
        )

    async def connect(self) -> None:
        if self._url:
            await self._connect_http()
        else:
            await self._connect_stdio()

    async def _connect_http(self) -> None:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        assert self._url is not None
        self._http_client = self._make_http_client()
        try:
            self._cm = streamable_http_client(self._url, http_client=self._http_client)
            opened = await self._cm.__aenter__()
            # MCP 1.x yields (read, write, get_session_id); 2.x yields (read, write).
            read, write = opened[0], opened[1]
            self._session = ClientSession(read, write)
            await self._session.__aenter__()
            await self._session.initialize()
        except Exception:
            await self.close()
            raise
        logger.info("mcp health connected: %s", self._url)

    async def _connect_stdio(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        assert self._command is not None
        parts = self._command.split()
        params = StdioServerParameters(command=parts[0], args=parts[1:], env=None)
        self._cm = stdio_client(params)
        try:
            read, write = await self._cm.__aenter__()
            self._session = ClientSession(read, write)
            await self._session.__aenter__()
            await self._session.initialize()
        except Exception:
            await self.close()
            raise
        logger.info("mcp health connected: %s", parts[0])

    async def close(self) -> None:
        if self._session is not None:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                logger.warning("mcp session close failed", exc_info=True)
            self._session = None
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:  # noqa: BLE001
                logger.warning("mcp transport close failed", exc_info=True)
            self._cm = None
        if self._http_client is not None:
            try:
                await self._http_client.aclose()
            except Exception:  # noqa: BLE001
                logger.warning("mcp http client close failed", exc_info=True)
            self._http_client = None

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
            schema = getattr(tool, "inputSchema", None)
            if schema is None:
                schema = getattr(tool, "input_schema", None)
            if not isinstance(schema, dict):
                schema = {}
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
        if len(out) > _MAX_TOOL_RESULT_CHARS:
            out = out[:_MAX_TOOL_RESULT_CHARS] + "…"
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
