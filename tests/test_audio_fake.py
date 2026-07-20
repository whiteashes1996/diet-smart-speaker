from smart_speaker.adapters.testing.fake_audio import FakeAudioIO


def test_fake_audio_capture_toggle_and_play_buffer():
    audio = FakeAudioIO()
    chunks = []
    audio.start_input(chunks.append)
    audio.inject_chunk(b"\x00\x01" * 100)
    assert chunks  # received
    audio.set_capture_enabled(False)
    n = len(chunks)
    audio.inject_chunk(b"\x00\x02" * 100)
    assert len(chunks) == n  # muted
    audio.play(b"\x03\x04" * 10)
    assert audio.played[-1] == b"\x03\x04" * 10
    audio.stop_input()
