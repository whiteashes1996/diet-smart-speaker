from smart_speaker.orchestrator.session import Session, truncate_tool_result


def test_truncate_tool_result():
    assert truncate_tool_result("abc", 10) == "abc"
    assert truncate_tool_result("x" * 2500).endswith("…")
    assert len(truncate_tool_result("x" * 2500)) == 2001


def test_session_keeps_last_eight():
    s = Session(max_messages=8)
    for i in range(12):
        s.add_user(f"u{i}")
        s.add_assistant(f"a{i}")
    assert len(s.messages) == 8
