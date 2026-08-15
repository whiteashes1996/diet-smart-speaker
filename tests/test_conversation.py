"""Tests for conversation (multi-turn) behavior in the orchestrator."""

from __future__ import annotations

import pytest

from smart_speaker.adapters.testing.fake_audio import FakeAudioIO
from smart_speaker.adapters.testing.fake_llm import FakeLLM
from smart_speaker.adapters.testing.fake_stt import FakeSTT
from smart_speaker.adapters.testing.fake_tools import FakeTools
from smart_speaker.adapters.testing.fake_tts import FakeTTS
from smart_speaker.adapters.testing.fake_wake import FakeWakeWord
from smart_speaker.adapters.tools.mcp_health import FilteringToolBackend
from smart_speaker.config import AppConfig
from smart_speaker.orchestrator.state_machine import Orchestrator, State


def _orch(**kwargs):
    cfg = AppConfig(conversation_idle_s=kwargs.pop("conversation_idle_s", 0.05))
    return Orchestrator(
        config=cfg,
        audio=kwargs.pop("audio", FakeAudioIO()),
        wake=kwargs.pop("wake", FakeWakeWord(trigger_after_chunks=1)),
        stt=kwargs.pop("stt", FakeSTT()),
        llm=kwargs.pop("llm", FakeLLM()),
        tts=kwargs.pop("tts", FakeTTS()),
        tools=kwargs.pop("tools", FilteringToolBackend(FakeTools())),
        wake_cue_pcm=b"\x00\x01" * 40,
        **kwargs,
    )


def _speech_frame():
    # loud square wave → RMS well above threshold
    return b"\xff\x7f" * 640


def _silence_frame():
    return b"\x00\x00" * 640


@pytest.mark.asyncio
async def test_second_turn_stays_in_conversation():
    stt = FakeSTT(text="你好")
    orch = _orch(stt=stt)
    orch._enter_conversation()
    orch._reset_listen()

    # feed speech then silence to finish utterance
    for _ in range(5):
        await orch._handle_chunk(_speech_frame())
    orch._vad._threshold = 500
    for _ in range(40):  # silence_ms default 1200 / 40ms frame = 30 frames
        await orch._handle_chunk(_silence_frame())

    # after answer it should go back to LISTENING (still in conversation), not IDLE
    assert orch._in_conversation is True
    assert orch.state == State.LISTENING


@pytest.mark.asyncio
async def test_idle_timeout_returns_to_wake():
    orch = _orch(conversation_idle_s=0.0)  # immediately time out
    orch._enter_conversation()
    orch._reset_listen()
    await orch._handle_chunk(_silence_frame())
    assert orch._in_conversation is False
    assert orch.state == State.IDLE
    assert orch.session.messages == []


@pytest.mark.asyncio
async def test_stt_fail_returns_to_listen_not_idle():
    orch = _orch(stt=FakeSTT(fail=True))
    orch._enter_conversation()
    orch._reset_listen()
    orch._utterance = bytearray(_speech_frame())
    await orch._finish_listening()
    assert orch._in_conversation is True
    assert orch.state == State.LISTENING


@pytest.mark.asyncio
async def test_single_turn_when_not_in_conversation():
    stt = FakeSTT(text="你好")
    orch = _orch(stt=stt)
    # simulate_wake_and_utterance without entering conversation → back to IDLE
    reply = await orch.simulate_wake_and_utterance(b"\x00\x01" * 100)
    assert reply
    assert orch.state == State.IDLE
    assert orch._in_conversation is False


@pytest.mark.asyncio
async def test_end_keyword_exits_conversation():
    stt = FakeSTT(text="好了结束对话")
    orch = _orch(stt=stt)
    orch._enter_conversation()
    orch._reset_listen()
    orch._utterance = bytearray(_speech_frame())
    await orch._finish_listening()
    assert orch._in_conversation is False
    assert orch.state == State.IDLE
    assert orch.session.messages == []


@pytest.mark.asyncio
async def test_short_transcript_skips_llm():
    stt = FakeSTT(text="嗯")
    llm = FakeLLM()
    orch = _orch(stt=stt, llm=llm)
    orch._enter_conversation()
    orch._reset_listen()
    orch._utterance = bytearray(_speech_frame())
    await orch._finish_listening()
    assert llm.calls == 0
    assert orch._in_conversation is True
    assert orch.state == State.LISTENING


@pytest.mark.asyncio
async def test_non_end_keyword_stays_in_conversation():
    stt = FakeSTT(text="我今天吃了汉堡")
    orch = _orch(stt=stt)
    orch._enter_conversation()
    orch._reset_listen()
    orch._utterance = bytearray(_speech_frame())
    await orch._finish_listening()
    assert orch._in_conversation is True
    assert orch.state == State.LISTENING
