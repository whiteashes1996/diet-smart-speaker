# Task Brief 0

## Global Constraints

- 音频格式：`pcm_s16le`，16kHz，mono（全链路统一）
- 唤醒词 v1 默认：`hey_jarvis`（openWakeWord 预置）
- 半双工：TTS/播放期间 `set_capture_enabled(False)`；v1 **不打断**
- VAD：静音 1.2s 结束话轮；最长录音 30s
- 会话：最近 8 条 user/assistant；单条 tool result ≤ 2k 字符
- Tool 循环：max 5 rounds；Thinking 超时 45s
- 时区：`Asia/Shanghai`；日期工具缺省当日 `YYYY-MM-DD`
- MCP 白名单仅：`log_food`, `list_foods`, `add_food`, `get_day`, `get_daily_summary`, `get_goals`, `get_trend`, `update_entry`, `delete_entry`
- 配置优先级：`env > config.yaml > defaults`
- 禁止：orchestrator import 云/MCP SDK；adapters 互相调用
- 仓库：私有 GitHub；每个 Task 完成后 `commit` + `push`
- **闸门规则：当前 Task 的自动化测试 +（若有）人工清单全部通过前，禁止开始下一 Task**

## Testing Philosophy

| 类型 | 用途 | 何时必须通过 |
|

### Task 0: 私有仓库 + 项目骨架 + Protocol

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `config.yaml.example`, `README.md`
- Create: `src/smart_speaker/errors.py`, `config.py`, `protocols/*.py`, `adapters/testing/*.py`（空壳可后填）
- Create: `tests/test_protocols_import.py`, `tests/test_config.py`
- Test: `tests/test_protocols_import.py`, `tests/test_config.py`

**Interfaces:**
- Produces: Protocol 类与 `AppConfig`；错误类型 `TransientError` / `FatalError`

- [ ] **Step 1: 初始化 git 与私有 GitHub**

```bash
cd "/Users/whiteashes/Documents/智能音箱"
git init
gh repo create smart-speaker --private --source=. --remote=origin --description "Mac/Pi diet voice assistant"
```

Expected: `gh repo view` 显示 private。

- [ ] **Step 2: 写 `pyproject.toml`**

```toml
[project]
name = "smart-speaker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "numpy>=1.26",
  "sounddevice>=0.5",
  "openwakeword>=0.6",
  "openai>=1.40",
  "edge-tts>=6.1",
  "mcp>=1.0",
  "pyyaml>=6.0",
  "python-dotenv>=1.0",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

[project.scripts]
smart-speaker = "smart_speaker.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/smart_speaker"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

- [ ] **Step 3: 写 Protocol 与错误类型（完整最小契约）**

`src/smart_speaker/errors.py`:

```python
class SmartSpeakerError(Exception):
    pass

class TransientError(SmartSpeakerError):
    """Retryable: network blip, empty STT, etc."""

class FatalError(SmartSpeakerError):
    """Non-retryable: missing mic permission, bad config."""
```

`src/smart_speaker/protocols/audio.py`:

```python
from typing import Callable, Protocol

class AudioIO(Protocol):
    def start_input(self, callback: Callable[[bytes], None]) -> None: ...
    def stop_input(self) -> None: ...
    def play(self, pcm: bytes) -> None: ...
    def set_capture_enabled(self, enabled: bool) -> None: ...
```

`src/smart_speaker/protocols/wake.py`:

```python
from typing import Protocol

class WakeWord(Protocol):
    def process_chunk(self, pcm: bytes) -> bool: ...
```

`src/smart_speaker/protocols/stt.py`:

```python
from typing import Protocol

class STT(Protocol):
    async def transcribe(self, pcm: bytes) -> str: ...
```

`src/smart_speaker/protocols/tts.py`:

```python
from typing import Protocol

class TTS(Protocol):
    async def synthesize(self, text: str) -> bytes: ...
```

`src/smart_speaker/protocols/llm.py`:

```python
from dataclasses import dataclass, field
from typing import Any, Protocol

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

@dataclass
class LLMResult:
    final_text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

class LLM(Protocol):
    async def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> LLMResult: ...
```

`src/smart_speaker/protocols/tools.py`:

```python
from dataclasses import dataclass
from typing import Any, Protocol

@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]

class ToolBackend(Protocol):
    def list_tools(self) -> list[ToolSpec]: ...
    async def call(self, name: str, arguments: dict[str, Any]) -> str: ...
```

`src/smart_speaker/protocols/__init__.py`：再导出上述符号。

- [ ] **Step 4: 写失败测试 `tests/test_protocols_import.py`**

```python
def test_protocols_export_core_types():
    from smart_speaker.protocols import AudioIO, WakeWord, STT, TTS, LLM, ToolBackend, LLMResult, ToolSpec
    assert AudioIO is not None
    assert LLMResult(final_text="ok").final_text == "ok"
    assert ToolSpec(name="x", description="d", parameters={}).name == "x"
```

- [ ] **Step 5: 运行确认失败或通过（骨架写完后应通过）**

```bash
cd "/Users/whiteashes/Documents/智能音箱"
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_protocols_import.py -v
```

Expected: PASS

- [ ] **Step 6: 写 `config.py` + 测试**

`src/smart_speaker/config.py`（要点）：dataclass `AppConfig`，字段含 `wake_word=hey_jarvis`、`sample_rate=16000`、`silence_ms=1200`、`max_listen_s=30`、`timezone=Asia/Shanghai`、`deepseek_api_key`、`stt_api_key`、`stt_base_url`、`mcp_health_command`；加载顺序 env > yaml > defaults。

`tests/test_config.py`：用 monkeypatch 设 env，断言覆盖 yaml。

- [ ] **Step 7: Commit + push**

```bash
git add -A
git commit -m "$(cat <<'EOF'
chore: scaffold protocols, config, and private-repo baseline

EOF
)"
git push -u origin HEAD
```

**Task 0 完成标准：** `pytest tests/test_protocols_import.py tests/test_config.py -v` 全绿；remote 已推送。

---

