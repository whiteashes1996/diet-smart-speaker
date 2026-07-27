import pytest

from smart_speaker.adapters.testing.fake_audio import FakeAudioIO
from smart_speaker.adapters.testing.fake_llm import FakeLLM, tool_then_text
from smart_speaker.adapters.testing.fake_stt import FakeSTT
from smart_speaker.adapters.testing.fake_tools import FakeTools
from smart_speaker.adapters.testing.fake_tts import FakeTTS
from smart_speaker.adapters.testing.fake_wake import FakeWakeWord
from smart_speaker.adapters.tools.mcp_health import FilteringToolBackend
from smart_speaker.config import AppConfig
from smart_speaker.orchestrator.state_machine import (
    PROMPT_MCP_FAIL,
    PROMPT_STT_FAIL,
    Orchestrator,
)


def _orch(**kwargs):
    cfg = AppConfig()
    audio = kwargs.pop("audio", FakeAudioIO())
    wake = kwargs.pop("wake", FakeWakeWord(trigger_after_chunks=1))
    stt = kwargs.pop("stt", FakeSTT())
    llm = kwargs.pop("llm", FakeLLM())
    tts = kwargs.pop("tts", FakeTTS())
    tools = kwargs.pop("tools", FilteringToolBackend(FakeTools()))
    return Orchestrator(
        config=cfg,
        audio=audio,
        wake=wake,
        stt=stt,
        llm=llm,
        tts=tts,
        tools=tools,
        wake_cue_pcm=b"\x00\x01" * 40,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_wake_listen_think_speak_with_fakes():
    audio = FakeAudioIO()
    stt = FakeSTT(text="今天中午吃了鸡蛋")
    orch = _orch(audio=audio, stt=stt)
    reply = await orch.simulate_wake_and_utterance(b"\x00\x01" * 1600)
    assert audio.played  # cue + reply
    assert "鸡蛋" in stt.last_input_or_text
    assert reply


@pytest.mark.asyncio
async def test_stt_transient_speaks_prompt():
    orch = _orch(stt=FakeSTT(fail=True))
    reply = await orch.simulate_wake_and_utterance(b"\x00\x01" * 100)
    assert reply == PROMPT_STT_FAIL


@pytest.mark.asyncio
async def test_tool_failure_message():
    tools = FilteringToolBackend(FakeTools(fail_call=True))
    llm = FakeLLM(results=tool_then_text())
    orch = _orch(tools=tools, llm=llm)
    reply = await orch.run_turn_from_pcm(b"\x00\x01" * 10, user_text_override="记一下鸡蛋")
    assert reply == PROMPT_MCP_FAIL


@pytest.mark.asyncio
async def test_max_tool_rounds():
    from smart_speaker.protocols.llm import LLMResult, ToolCall

    endless = [
        LLMResult(tool_calls=[ToolCall(id=str(i), name="log_food", arguments={})])
        for i in range(6)
    ]
    orch = _orch(llm=FakeLLM(results=endless), max_tool_rounds=5)
    reply = await orch.run_turn_from_pcm(b"\x00\x01" * 10, user_text_override="记")
    assert "步骤有点多" in reply


@pytest.mark.asyncio
async def test_speaking_disables_capture():
    audio = FakeAudioIO()
    toggles: list[bool] = []
    orig = audio.set_capture_enabled

    def track(enabled: bool) -> None:
        toggles.append(enabled)
        orig(enabled)

    audio.set_capture_enabled = track  # type: ignore[method-assign]
    orch = _orch(audio=audio)
    await orch.simulate_wake_and_utterance(b"\x00\x01" * 100)
    assert False in toggles
