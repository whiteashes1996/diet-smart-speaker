"""Unit tests for remote/stdio health MCP backend (no live network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from smart_speaker.adapters.tools.local_notes import LocalNoteToolBackend, MultiToolBackend
from smart_speaker.adapters.testing.fake_tools import FakeTools
from smart_speaker.adapters.tools import mcp_health as mcp_health_mod
from smart_speaker.adapters.tools.mcp_health import (
    DIET_TOOL_WHITELIST,
    FilteringToolBackend,
    McpHealthToolBackend,
    build_mcp_health_backend,
    resolve_mcp_health_token,
)
from smart_speaker.config import AppConfig
from smart_speaker.errors import FatalError, TransientError
from smart_speaker.protocols.tools import ToolSpec


class _FakeTool:
    def __init__(
        self,
        name: str,
        description: str = "",
        schema: dict | None = None,
        *,
        snake_schema: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        payload = schema if schema is not None else {"type": "object"}
        if snake_schema:
            self.input_schema = payload
        else:
            self.inputSchema = payload


class _FakeSession:
    def __init__(self, tools: list[_FakeTool] | None = None, call_text: str = '{"ok":true}') -> None:
        self.tools = tools or [
            _FakeTool("log_food", "record food"),
            _FakeTool("get_day", "day view"),
            _FakeTool("list_transactions", "money — must be filtered"),
            _FakeTool("add_task", "task — must be filtered"),
        ]
        self.call_text = call_text
        self.calls: list[tuple[str, dict]] = []
        self.fail = False

    async def list_tools(self):
        return SimpleNamespace(tools=self.tools)

    async def call_tool(self, name: str, arguments: dict):
        self.calls.append((name, arguments))
        if self.fail:
            raise RuntimeError("mcp down")
        return SimpleNamespace(content=[SimpleNamespace(text=self.call_text)])


def test_resolve_token_prefers_inline():
    cfg = AppConfig(mcp_health_token="  abc  ", mcp_health_token_file="/no/such")
    assert resolve_mcp_health_token(cfg) == "abc"


def test_resolve_token_from_file(tmp_path):
    path = tmp_path / "user1.token"
    path.write_text("  hm_file_token  \n", encoding="utf-8")
    cfg = AppConfig(mcp_health_token_file=str(path))
    assert resolve_mcp_health_token(cfg) == "hm_file_token"


def test_resolve_token_file_missing(tmp_path):
    cfg = AppConfig(mcp_health_token_file=str(tmp_path / "missing.token"))
    assert resolve_mcp_health_token(cfg) is None


def test_resolve_token_file_empty(tmp_path):
    path = tmp_path / "empty.token"
    path.write_text("   \n", encoding="utf-8")
    cfg = AppConfig(mcp_health_token_file=str(path))
    assert resolve_mcp_health_token(cfg) is None


def test_resolve_token_none():
    assert resolve_mcp_health_token(AppConfig()) is None


def test_resolve_token_expands_user(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "tok").write_text("hm_home\n", encoding="utf-8")
    cfg = AppConfig(mcp_health_token_file="~/tok")
    assert resolve_mcp_health_token(cfg) == "hm_home"


def test_build_returns_none_when_unconfigured():
    assert build_mcp_health_backend(AppConfig()) is None


def test_build_prefers_url_over_command():
    cfg = AppConfig(
        mcp_health_url="https://47.94.4.180:8443/mcp",
        mcp_health_token="hm_user1",
        mcp_health_command="/bin/health-mcp",
    )
    backend = build_mcp_health_backend(cfg)
    assert backend is not None
    assert backend._url == "https://47.94.4.180:8443/mcp"
    assert backend._token == "hm_user1"
    assert backend._command is None


def test_build_url_requires_token():
    cfg = AppConfig(mcp_health_url="https://47.94.4.180:8443/mcp")
    with pytest.raises(FatalError, match="MCP_HEALTH_TOKEN"):
        build_mcp_health_backend(cfg)


def test_build_url_reads_token_file(tmp_path):
    path = tmp_path / "tok"
    path.write_text("hm_from_file\n", encoding="utf-8")
    cfg = AppConfig(
        mcp_health_url="https://47.94.4.180:8443/mcp",
        mcp_health_token_file=str(path),
        mcp_health_ca_file="~/ca.pem",
    )
    backend = build_mcp_health_backend(cfg)
    assert backend is not None
    assert backend._token == "hm_from_file"
    assert backend._ca_file == "~/ca.pem"


def test_build_stdio_when_no_url():
    backend = build_mcp_health_backend(AppConfig(mcp_health_command="/bin/health-mcp serve"))
    assert backend is not None
    assert backend._command == "/bin/health-mcp serve"
    assert backend._url is None


def test_init_requires_url_or_command():
    with pytest.raises(FatalError, match="MCP_HEALTH_URL or MCP_HEALTH_COMMAND"):
        McpHealthToolBackend()


def test_init_url_requires_token():
    with pytest.raises(FatalError, match="MCP_HEALTH_TOKEN"):
        McpHealthToolBackend(url="https://example/mcp")


def test_init_positional_command_still_works():
    backend = McpHealthToolBackend("/bin/health-mcp")
    assert backend._command == "/bin/health-mcp"


def test_http_client_sets_bearer_and_skips_proxy(monkeypatch):
    captured: dict = {}

    def wrapper(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kwargs=kwargs)

    monkeypatch.setattr(mcp_health_mod, "_async_http_client_cls", lambda: wrapper)
    backend = McpHealthToolBackend(url="https://47.94.4.180:8443/mcp", token="hm_user1")
    backend._make_http_client()
    assert captured["headers"]["Authorization"] == "Bearer hm_user1"
    assert "application/json" in captured["headers"]["Accept"]
    assert "text/event-stream" in captured["headers"]["Accept"]
    assert captured["trust_env"] is False
    assert captured["verify"] is False


def test_http_client_uses_ca_file_when_present(tmp_path, monkeypatch):
    import ssl

    captured: dict = {}
    fake_ctx = object()

    def fake_create_default_context(cafile=None):
        captured["cafile"] = cafile
        return fake_ctx

    def wrapper(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kwargs=kwargs)

    monkeypatch.setattr(mcp_health_mod, "_async_http_client_cls", lambda: wrapper)
    monkeypatch.setattr(ssl, "create_default_context", fake_create_default_context)
    ca = tmp_path / "ca.pem"
    ca.write_text("placeholder-ca\n", encoding="utf-8")
    backend = McpHealthToolBackend(
        url="https://47.94.4.180:8443/mcp",
        token="hm_user1",
        ca_file=str(ca),
    )
    backend._make_http_client()
    assert captured["cafile"] == str(ca)
    assert captured["verify"] is fake_ctx


def test_http_client_missing_ca_file_disables_verify(tmp_path, monkeypatch):
    captured: dict = {}

    def wrapper(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(kwargs=kwargs)

    monkeypatch.setattr(mcp_health_mod, "_async_http_client_cls", lambda: wrapper)
    backend = McpHealthToolBackend(
        url="https://47.94.4.180:8443/mcp",
        token="hm_user1",
        ca_file=str(tmp_path / "missing.pem"),
    )
    backend._make_http_client()
    assert captured["verify"] is False


def test_list_tools_before_refresh_raises():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    with pytest.raises(FatalError, match="not loaded"):
        backend.list_tools()


@pytest.mark.asyncio
async def test_refresh_tools_requires_session():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    with pytest.raises(FatalError, match="not connected"):
        await backend.refresh_tools()


@pytest.mark.asyncio
async def test_refresh_tools_keeps_only_diet_whitelist():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    backend._session = _FakeSession()
    specs = await backend.refresh_tools()
    names = [s.name for s in specs]
    assert names == ["log_food", "get_day"]
    assert set(names) <= DIET_TOOL_WHITELIST
    assert backend.list_tools()[0].description == "record food"
    assert backend.list_tools()[0].parameters == {"type": "object"}


@pytest.mark.asyncio
async def test_refresh_tools_reads_mcp2_input_schema():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    backend._session = _FakeSession(
        tools=[_FakeTool("log_food", "record", {"type": "object", "properties": {"name": {}}}, snake_schema=True)]
    )
    specs = await backend.refresh_tools()
    assert specs[0].parameters["properties"]["name"] == {}


@pytest.mark.asyncio
async def test_call_rejects_non_whitelist_without_hitting_session():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    session = _FakeSession()
    backend._session = session
    out = await backend.call("list_transactions", {"start": "2026-01-01"})
    assert "not allowed" in out
    assert session.calls == []


@pytest.mark.asyncio
async def test_call_when_disconnected():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    out = await backend.call("log_food", {"name": "鸡蛋", "meal": "午", "date": "2026-08-15"})
    assert "not connected" in out


@pytest.mark.asyncio
async def test_call_log_food_forwards_args_without_user():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    session = _FakeSession(call_text='{"id":1,"name":"鸡蛋"}')
    backend._session = session
    args = {"name": "鸡蛋", "pieces": 2, "meal": "午", "date": "2026-08-15"}
    out = await backend.call("log_food", args)
    assert session.calls == [("log_food", args)]
    assert "user" not in session.calls[0][1]
    assert "鸡蛋" in out


@pytest.mark.asyncio
async def test_call_truncates_long_result():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    backend._session = _FakeSession(call_text="x" * 2500)
    out = await backend.call("get_day", {"date": "2026-08-15"})
    assert out.endswith("…")
    assert len(out) == 2001


@pytest.mark.asyncio
async def test_call_empty_content_returns_ok_json():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")

    class EmptySession:
        async def call_tool(self, name, arguments):
            return SimpleNamespace(content=[])

    backend._session = EmptySession()
    out = await backend.call("get_goals", {})
    assert '"ok": true' in out


@pytest.mark.asyncio
async def test_call_non_text_block_stringified():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")

    class BlockSession:
        async def call_tool(self, name, arguments):
            return SimpleNamespace(content=[SimpleNamespace(kind="image")])

    backend._session = BlockSession()
    out = await backend.call("get_goals", {})
    assert "image" in out


@pytest.mark.asyncio
async def test_call_session_error_is_transient():
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    session = _FakeSession()
    session.fail = True
    backend._session = session
    with pytest.raises(TransientError, match="MCP call failed"):
        await backend.call("log_food", {"name": "鸡蛋", "meal": "午", "date": "2026-08-15"})


@pytest.mark.asyncio
async def test_connect_http_initializes_and_passes_client(monkeypatch):
    captured: dict = {}

    class FakeCM:
        async def __aenter__(self):
            return ("read", "write", lambda: "sid")

        async def __aexit__(self, *exc):
            captured["cm_closed"] = True
            return False

    class FakeSession:
        def __init__(self, read, write):
            captured["session_streams"] = (read, write)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            captured["session_closed"] = True
            return False

        async def initialize(self):
            captured["initialized"] = True

    def fake_streamable(url, *, http_client=None, terminate_on_close=True):
        captured["url"] = url
        captured["http_client"] = http_client
        captured["terminate_on_close"] = terminate_on_close
        return FakeCM()

    mcp_mod = SimpleNamespace(ClientSession=FakeSession, StdioServerParameters=object)
    monkeypatch.setitem(__import__("sys").modules, "mcp", mcp_mod)
    monkeypatch.setitem(__import__("sys").modules, "mcp.client", SimpleNamespace())
    monkeypatch.setitem(
        __import__("sys").modules,
        "mcp.client.streamable_http",
        SimpleNamespace(streamable_http_client=fake_streamable),
    )

    backend = McpHealthToolBackend(url="https://47.94.4.180:8443/mcp", token="hm_user1")
    await backend.connect()
    assert captured["url"] == "https://47.94.4.180:8443/mcp"
    assert captured["http_client"] is backend._http_client
    assert captured["initialized"] is True
    assert captured["session_streams"] == ("read", "write")
    assert backend._http_client.headers["Authorization"] == "Bearer hm_user1"

    await backend.close()
    assert captured["session_closed"] is True
    assert captured["cm_closed"] is True
    assert backend._session is None
    assert backend._http_client is None


@pytest.mark.asyncio
async def test_connect_http_accepts_two_stream_tuple(monkeypatch):
    captured: dict = {}

    class FakeCM:
        async def __aenter__(self):
            return ("read2", "write2")

        async def __aexit__(self, *exc):
            return False

    class FakeSession:
        def __init__(self, read, write):
            captured["session_streams"] = (read, write)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def initialize(self):
            captured["initialized"] = True

    monkeypatch.setitem(__import__("sys").modules, "mcp", SimpleNamespace(ClientSession=FakeSession))
    monkeypatch.setitem(__import__("sys").modules, "mcp.client", SimpleNamespace())
    monkeypatch.setitem(
        __import__("sys").modules,
        "mcp.client.streamable_http",
        SimpleNamespace(streamable_http_client=lambda *a, **k: FakeCM()),
    )
    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    await backend.connect()
    assert captured["session_streams"] == ("read2", "write2")
    assert captured["initialized"] is True
    await backend.close()


@pytest.mark.asyncio
async def test_connect_http_failure_closes_client(monkeypatch):
    class BoomCM:
        async def __aenter__(self):
            raise RuntimeError("handshake failed")

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setitem(
        __import__("sys").modules,
        "mcp",
        SimpleNamespace(ClientSession=object, StdioServerParameters=object),
    )
    monkeypatch.setitem(__import__("sys").modules, "mcp.client", SimpleNamespace())
    monkeypatch.setitem(
        __import__("sys").modules,
        "mcp.client.streamable_http",
        SimpleNamespace(streamable_http_client=lambda *a, **k: BoomCM()),
    )

    backend = McpHealthToolBackend(url="https://example/mcp", token="t")
    with pytest.raises(RuntimeError, match="handshake failed"):
        await backend.connect()
    assert backend._session is None
    assert backend._http_client is None


@pytest.mark.asyncio
async def test_multi_backend_keeps_notes_and_filtered_diet(tmp_path):
    notes = LocalNoteToolBackend(memory_dir=tmp_path / "mem")
    health = FilteringToolBackend(FakeTools())
    multi = MultiToolBackend([health, notes])
    names = {t.name for t in multi.list_tools()}
    assert "log_food" in names
    assert "get_daily_summary" in names
    assert "save_note" in names
    assert "search_notes" in names
    assert "add_task" not in names

    await multi.call("save_note", {"content": "我对花生过敏"})
    found = await multi.call("search_notes", {"query": "花生"})
    assert "花生过敏" in found
    diet = await multi.call("log_food", {"name": "鸡蛋", "meal": "午"})
    assert '"ok": true' in diet
