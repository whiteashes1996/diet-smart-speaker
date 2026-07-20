from smart_speaker.adapters.testing.fake_wake import FakeWakeWord


def test_fake_wake_triggers_on_marker_chunk():
    wake = FakeWakeWord(trigger_after_chunks=3)
    assert wake.process_chunk(b"\x00" * 1280) is False
    assert wake.process_chunk(b"\x00" * 1280) is False
    assert wake.process_chunk(b"\x00" * 1280) is True
