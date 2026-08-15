"""Tests for LocalNoteToolBackend and MultiToolBackend."""

from __future__ import annotations

import pytest

from smart_speaker.adapters.tools.local_notes import (
    LocalNoteToolBackend,
    MultiToolBackend,
)


@pytest.fixture
def notes(tmp_path):
    return LocalNoteToolBackend(memory_dir=tmp_path / "mem")


@pytest.mark.asyncio
async def test_save_and_search_note(notes):
    out = await notes.call("save_note", {"content": "我对花生过敏", "tags": "过敏,饮食"})
    assert '"ok": true' in out

    res = await notes.call("search_notes", {"query": "花生"})
    assert "花生过敏" in res
    assert '"count": 1' in res


@pytest.mark.asyncio
async def test_search_multi_term(notes):
    await notes.call("save_note", {"content": "明天下午三点提醒我买菜"})
    await notes.call("save_note", {"content": "我不吃香菜"})

    res = await notes.call("search_notes", {"query": "提醒 买菜"})
    assert "提醒我买菜" in res
    assert "香菜" not in res


@pytest.mark.asyncio
async def test_search_no_match(notes):
    await notes.call("save_note", {"content": "我喜欢跑步"})
    res = await notes.call("search_notes", {"query": "游泳"})
    assert '"count": 0' in res


@pytest.mark.asyncio
async def test_list_notes_newest_first(notes):
    await notes.call("save_note", {"content": "第一条"})
    await notes.call("save_note", {"content": "第二条"})
    res = await notes.call("list_notes", {"limit": 5})
    # newest first
    assert res.index("第二条") < res.index("第一条")
    assert '"total": 2' in res


@pytest.mark.asyncio
async def test_save_note_empty(notes):
    out = await notes.call("save_note", {"content": "  "})
    assert '"error"' in out


@pytest.mark.asyncio
async def test_multi_backend_routing(notes, tmp_path):
    other = LocalNoteToolBackend(memory_dir=tmp_path / "other")
    multi = MultiToolBackend([notes, other])
    names = [t.name for t in multi.list_tools()]
    # both expose same names; first backend wins in routing
    assert "save_note" in names
    await multi.call("save_note", {"content": "路由测试"})
    assert '"count": 1' in await notes.call("search_notes", {"query": "路由"})
    assert '"count": 0' in await other.call("search_notes", {"query": "路由"})


@pytest.mark.asyncio
async def test_multi_backend_unknown_tool(notes):
    multi = MultiToolBackend([notes])
    out = await multi.call("does_not_exist", {})
    assert '"error"' in out
