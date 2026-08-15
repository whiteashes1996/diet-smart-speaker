import json

import pytest

from smart_speaker.adapters.testing.fake_tools import FakeTools
from smart_speaker.adapters.tools.mcp_health import DIET_TOOL_WHITELIST, FilteringToolBackend
from smart_speaker.protocols.tools import ToolSpec


def test_mcp_whitelist_constant_complete():
    expected = {
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
    assert DIET_TOOL_WHITELIST == expected


def test_list_tools_excludes_non_whitelist():
    inner = FakeTools(
        tools=[
            ToolSpec(name="log_food", description="", parameters={}),
            ToolSpec(name="list_transactions", description="", parameters={}),
        ]
    )
    names = [t.name for t in FilteringToolBackend(inner).list_tools()]
    assert names == ["log_food"]


@pytest.mark.asyncio
async def test_filtering_allows_whitelisted_call():
    inner = FakeTools()
    backend = FilteringToolBackend(inner)
    out = await backend.call("log_food", {"name": "鸡蛋", "meal": "午"})
    assert json.loads(out)["ok"] is True
    assert inner.calls == [("log_food", {"name": "鸡蛋", "meal": "午"})]


@pytest.mark.asyncio
async def test_filtering_blocks_non_whitelist_call():
    inner = FakeTools()
    backend = FilteringToolBackend(inner)
    out = await backend.call("list_transactions", {})
    assert "not allowed" in out
    assert inner.calls == []
