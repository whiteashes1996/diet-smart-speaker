import pytest

from smart_speaker.adapters.testing.fake_tts import FakeTTS
from smart_speaker.adapters.tts.edge_tts_tts import EdgeTTSAdapter
from smart_speaker.errors import TransientError


@pytest.mark.asyncio
async def test_fake_tts_rejects_empty():
    tts = FakeTTS()
    with pytest.raises(TransientError):
        await tts.synthesize("  ")


@pytest.mark.asyncio
async def test_fake_tts_returns_pcm():
    tts = FakeTTS(pcm=b"\x01\x02" * 10)
    out = await tts.synthesize("已记录两个鸡蛋")
    assert out == b"\x01\x02" * 10


@pytest.mark.asyncio
async def test_edge_tts_empty_raises(monkeypatch):
    tts = EdgeTTSAdapter()

    async def boom(text: str):
        return b""

    monkeypatch.setattr(tts, "_fetch_mp3", boom)
    with pytest.raises(TransientError):
        await tts.synthesize("hello")


@pytest.mark.asyncio
async def test_edge_tts_mocked_pipeline(monkeypatch):
    tts = EdgeTTSAdapter()

    async def fake_mp3(text: str):
        return b"fake-mp3"

    monkeypatch.setattr(tts, "_fetch_mp3", fake_mp3)
    monkeypatch.setattr(tts, "_mp3_to_pcm", lambda mp3: b"\x00\x01" * 100)
    out = await tts.synthesize("你好")
    assert len(out) == 200
