import pytest

from smart_speaker.adapters.stt.openai_whisper_stt import OpenAIWhisperSTT
from smart_speaker.errors import TransientError


@pytest.mark.asyncio
async def test_transcribe_returns_text(monkeypatch):
    stt = OpenAIWhisperSTT(api_key="k", base_url="https://example.invalid/v1", model="whisper-1")

    async def fake_transcribe_file(**kwargs):
        class R:
            text = "今天中午吃了鸡蛋"

        return R()

    monkeypatch.setattr(stt, "_transcribe_file", fake_transcribe_file)
    text = await stt.transcribe(b"\x00\x01" * 16000)
    assert "鸡蛋" in text


@pytest.mark.asyncio
async def test_empty_transcript_raises_transient(monkeypatch):
    stt = OpenAIWhisperSTT(api_key="k", base_url="https://example.invalid/v1", model="whisper-1")

    async def fake_transcribe_file(**kwargs):
        class R:
            text = "  "

        return R()

    monkeypatch.setattr(stt, "_transcribe_file", fake_transcribe_file)
    with pytest.raises(TransientError):
        await stt.transcribe(b"\x00\x01" * 16000)
