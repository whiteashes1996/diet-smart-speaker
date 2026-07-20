def test_protocols_export_core_types():
    from smart_speaker.protocols import AudioIO, WakeWord, STT, TTS, LLM, ToolBackend, LLMResult, ToolSpec

    assert AudioIO is not None
    assert LLMResult(final_text="ok").final_text == "ok"
    assert ToolSpec(name="x", description="d", parameters={}).name == "x"
