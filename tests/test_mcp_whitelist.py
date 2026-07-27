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
