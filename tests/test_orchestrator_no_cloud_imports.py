import ast
from pathlib import Path

FORBIDDEN = {"openai", "edge_tts", "mcp", "openwakeword", "sounddevice"}


def test_orchestrator_has_no_forbidden_imports():
    root = Path("src/smart_speaker/orchestrator")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in FORBIDDEN, path
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in FORBIDDEN, path
