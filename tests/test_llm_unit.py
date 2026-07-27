import json

import pytest

from smart_speaker.adapters.llm.deepseek_llm import DeepSeekLLM
from smart_speaker.adapters.testing.fake_tools import FakeTools
from smart_speaker.adapters.tools.mcp_health import DIET_TOOL_WHITELIST, FilteringToolBackend
from smart_speaker.protocols.llm import LLMResult
from smart_speaker.protocols.tools import ToolSpec


def test_whitelist_filters_non_diet_tools():
    inner = FakeTools(
        tools=[
            ToolSpec(name="log_food", description="d", parameters={}),
            ToolSpec(name="add_task", description="nope", parameters={}),
            ToolSpec(name="get_day", description="d", parameters={}),
        ]
    )
    backend = FilteringToolBackend(inner)
    names = {t.name for t in backend.list_tools()}
    assert names == {"log_food", "get_day"}
    assert "add_task" not in names
    assert names <= DIET_TOOL_WHITELIST


@pytest.mark.asyncio
async def test_filtering_blocks_disallowed_call():
    backend = FilteringToolBackend(FakeTools())
    out = await backend.call("add_task", {"title": "x"})
    assert "not allowed" in out


@pytest.mark.asyncio
async def test_deepseek_final_text(monkeypatch):
    llm = DeepSeekLLM(api_key="k")

    class Msg:
        content = "你好"
        tool_calls = None

    class Choice:
        message = Msg()

    class Resp:
        choices = [Choice()]

    async def fake_create(**kwargs):
        return Resp()

    monkeypatch.setattr(llm, "_create", fake_create)
    result = await llm.chat([{"role": "user", "content": "hi"}], [])
    assert result.final_text == "你好"
    assert result.tool_calls == []


@pytest.mark.asyncio
async def test_deepseek_tool_calls(monkeypatch):
    llm = DeepSeekLLM(api_key="k")

    class Fn:
        name = "log_food"
        arguments = json.dumps({"name": "鸡蛋", "pieces": 2})

    class TC:
        id = "call1"
        function = Fn()

    class Msg:
        content = None
        tool_calls = [TC()]

    class Choice:
        message = Msg()

    class Resp:
        choices = [Choice()]

    async def fake_create(**kwargs):
        return Resp()

    monkeypatch.setattr(llm, "_create", fake_create)
    result = await llm.chat([], [{"type": "function", "function": {"name": "log_food"}}])
    assert result.final_text is None
    assert result.tool_calls[0].name == "log_food"
    assert result.tool_calls[0].arguments["pieces"] == 2
