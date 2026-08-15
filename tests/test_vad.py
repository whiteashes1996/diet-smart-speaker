import struct

from smart_speaker.orchestrator.vad import SilenceVAD, is_speech


def _tone(amplitude: int = 3000, samples: int = 640) -> bytes:
    return struct.pack("<" + "h" * samples, *([amplitude] * samples))


def _silence(samples: int = 640) -> bytes:
    return b"\x00\x00" * samples


def test_is_speech_detects_energy():
    assert is_speech(_tone()) is True
    assert is_speech(_silence()) is False
    assert is_speech(_tone(amplitude=800), threshold=1500) is False
    assert is_speech(_tone(amplitude=2000), threshold=1500) is True


def test_silence_vad_ends_after_silence():
    vad = SilenceVAD(silence_ms=120, frame_ms=40)
    assert vad.push(_tone()) == "continue"
    assert vad.push(_silence()) == "continue"
    assert vad.push(_silence()) == "continue"
    assert vad.push(_silence()) == "end_utterance"
