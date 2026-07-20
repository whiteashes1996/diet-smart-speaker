# Smart Speaker (Diet Voice Assistant) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Mac 上交付可移植到树莓派的饮食语音助手：唤醒 → STT → DeepSeek(+health MCP) → TTS，模块可替换，私有 GitHub 持续同步。

**Architecture:** 单一 Python 进程内状态机编排；六大 Protocol（AudioIO / WakeWord / STT / LLM / TTS / ToolBackend）由 adapter 注入；orchestrator 不直接依赖云 SDK 或 MCP SDK；Speaking 半双工 mute，播完再听。

**Tech Stack:** Python 3.11+、sounddevice、numpy、openWakeWord、OpenAI-compatible Whisper API、DeepSeek tool calling、edge-tts、MCP Python client（stdio）、pytest、pytest-asyncio。

**Spec:** `~/.gstack/projects/smart-speaker/whiteashes-unknown-design-20260720-193406.md`（Status: APPROVED）

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
|------|------|----------------|
| 单元测试（pytest） | 假依赖、纯逻辑、状态机 | 每个 Task 结束前 |
| 模块脚本（`scripts/manual_*`） | 真人麦克风/耳朵验收 | Task 2、Task 3 **硬闸门** |
| 集成测试（fake adapters） | 全状态机不碰硬件 | Task 7 前 |

### 人工介入硬闸门（必须遵守）

```text
Task 2 (Wake) 人工清单签字  ──► 才允许开始 Task 3 (STT)
Task 3 (STT)  人工清单签字  ──► 才允许开始 Task 4+
```

执行代理在未看到用户明确回复「唤醒人工验收通过」/「STT 人工验收通过」前，**不得**开始下一 Task。

---

## File Map

```text
smart-speaker/                          # 仓库根 = 工作区 /Users/whiteashes/Documents/智能音箱
  README.md
  pyproject.toml
  .env.example
  .gitignore
  config.yaml.example
  assets/wake_cue.wav                   # 短提示音（Task 2 生成或放入）
  src/smart_speaker/
    __init__.py
    config.py                           # 加载 env + yaml
    errors.py                           # TransientError / FatalError
    protocols/
      __init__.py
      audio.py
      wake.py
      stt.py
      llm.py
      tts.py
      tools.py
    adapters/
      audio/sounddevice_io.py
      wake/openwakeword_wake.py
      stt/openai_whisper_stt.py
      llm/deepseek_llm.py
      tts/edge_tts_tts.py
      tools/mcp_health.py
      testing/                          # 假实现，单测与集成用
        fake_audio.py
        fake_wake.py
        fake_stt.py
        fake_llm.py
        fake_tts.py
        fake_tools.py
    orchestrator/
      __init__.py
      state_machine.py
      vad.py
      session.py
    cli.py                              # python -m smart_speaker
  scripts/
    manual_wake_test.py                 # 人工：仅唤醒
    manual_stt_test.py                  # 人工：仅 STT（需唤醒已通过）
    generate_wake_cue.py
  tests/
    test_protocols_import.py
    test_config.py
    test_vad.py
    test_session.py
    test_wake_unit.py
    test_stt_unit.py
    test_tts_unit.py
    test_llm_unit.py
    test_mcp_whitelist.py
    test_state_machine.py
    test_orchestrator_no_cloud_imports.py
```

---

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

### Task 1: AudioIO（sounddevice）— 自动化 + 最短人工烟测

**Files:**
- Create: `src/smart_speaker/adapters/audio/sounddevice_io.py`
- Create: `src/smart_speaker/adapters/testing/fake_audio.py`
- Create: `tests/test_audio_fake.py`
- Create: `scripts/manual_audio_smoke.py`（可选 30 秒录放）

**Interfaces:**
- Consumes: `AudioIO` Protocol；`AppConfig.sample_rate`
- Produces: `SoundDeviceAudioIO` 实现四方法；chunk 建议 1280 bytes（40ms@16k s16le）或 80ms 帧，与 Wake 一致

- [ ] **Step 1: FakeAudio 单测（先写测试）**

```python
# tests/test_audio_fake.py
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
```

- [ ] **Step 2: 实现 `FakeAudioIO`，跑通单测**

- [ ] **Step 3: 实现 `SoundDeviceAudioIO`**

要求：`start_input` 在后台线程读流并 callback；callback 内禁止网络；`set_capture_enabled(False)` 时丢弃 chunk；`play` 阻塞至结束。

- [ ] **Step 4: 人工烟测（非硬闸门，但建议做）**

```bash
python scripts/manual_audio_smoke.py
# 对着麦说 3 秒，应回放听到自己的声音
```

通过条件：能听到回放。失败则查系统麦克风权限（macOS 设置 → 隐私 → 麦克风）。

- [ ] **Step 5: Commit + push**

```bash
git commit -m "feat(audio): add SoundDeviceAudioIO and FakeAudioIO"
git push
```

**Task 1 完成标准：** `pytest tests/test_audio_fake.py -v` PASS；人工回放可选但推荐。

---

### Task 2: WakeWord 模块 — 单元测试后 **人工硬闸门**

**Files:**
- Create: `src/smart_speaker/adapters/wake/openwakeword_wake.py`
- Create: `src/smart_speaker/adapters/testing/fake_wake.py`
- Create: `tests/test_wake_unit.py`
- Create: `scripts/manual_wake_test.py`
- Create: `scripts/generate_wake_cue.py` + `assets/wake_cue.wav`
- Create: `docs/manual-gates.md`（记录人工签字）

**Interfaces:**
- Consumes: `WakeWord.process_chunk(pcm: bytes) -> bool`；AudioIO 仅由 manual 脚本组合
- Produces: `OpenWakeWordWake`；检测到返回 True 后应有内部 refractory（如 2s 内不再触发）

#### 2A — 自动化

- [ ] **Step 1: 写 `tests/test_wake_unit.py`（Fake）**

```python
from smart_speaker.adapters.testing.fake_wake import FakeWakeWord

def test_fake_wake_triggers_on_marker_chunk():
    wake = FakeWakeWord(trigger_after_chunks=3)
    assert wake.process_chunk(b"\x00" * 1280) is False
    assert wake.process_chunk(b"\x00" * 1280) is False
    assert wake.process_chunk(b"\x00" * 1280) is True
```

- [ ] **Step 2: 实现 FakeWakeWord，测试 PASS**

- [ ] **Step 3: 实现 OpenWakeWordWake**

```python
# 要点伪代码 — 实现时写成完整可运行类
class OpenWakeWordWake:
    def __init__(self, model_name: str = "hey_jarvis", threshold: float = 0.5):
        from openwakeword.model import Model
        self._model = Model(wakeword_models=[model_name])
        self._threshold = threshold
        self._cooldown_chunks = 0

    def process_chunk(self, pcm: bytes) -> bool:
        import numpy as np
        if self._cooldown_chunks > 0:
            self._cooldown_chunks -= 1
            return False
        audio = np.frombuffer(pcm, dtype=np.int16)
        scores = self._model.predict(audio)
        score = float(max(scores.values())) if scores else 0.0
        if score >= self._threshold:
            self._cooldown_chunks = 50  # ~2s @ 40ms
            return True
        return False
```

- [ ] **Step 4: 生成提示音**

```bash
python scripts/generate_wake_cue.py  # 写出 assets/wake_cue.wav（短 beep）
```

- [ ] **Step 5: 写 `scripts/manual_wake_test.py`**

行为：
1. 打印：「请说 hey jarvis。检测到会播放提示音并在终端打印 WAKE_OK」
2. `AudioIO.start_input` → 每 chunk 喂 `WakeWord`
3. 首次 True：`set_capture_enabled(False)` → `play(wake_cue)` → 打印 `WAKE_OK` 与时间戳 → 退出码 0
4. 60s 未检测到：退出码 2，打印 `WAKE_TIMEOUT`
5. 日志文件：`/tmp/smart-speaker-wake-manual.log`

- [ ] **Step 6: 自动化回归**

```bash
pytest tests/test_wake_unit.py tests/test_audio_fake.py -v
```

Expected: PASS（**不要**在 CI 跑真实 openWakeWord 麦克风测试）

- [ ] **Step 7: Commit + push（人工前也可先推脚本）**

```bash
git commit -m "feat(wake): openWakeWord adapter and manual wake test script"
git push
```

#### 2B — 人工硬闸门（必须真人）

- [ ] **Step 8: 运行人工唤醒测试**

```bash
source .venv/bin/activate
python scripts/manual_wake_test.py
```

**通过清单（全部勾选才算过）：**

1. 说出 `hey jarvis` 后 **1 秒内** 终端出现 `WAKE_OK`
2. 听到 `wake_cue` 提示音
3. 安静环境站桩 **2 分钟**，误触发次数 **≤ 0**（若 1 次，调高 threshold 重测；仍失败则记录阈值后暂停找原因，不进入 Task 3）
4. 连续成功唤醒 **3 / 3** 次
5. 在 `docs/manual-gates.md` 追加：

```markdown
## Wake gate
- Date:
- Tester:
- Result: PASS
- Threshold used:
- Notes:
```

- [ ] **Step 9: 用户在对话中明确回复：`唤醒人工验收通过`**

**⛔ STOP：** 未完成 Step 8–9 前，禁止开始 Task 3。

**Task 2 完成标准：** 单元测试绿 + `docs/manual-gates.md` 有 Wake PASS + 用户口头确认。

---

### Task 3: STT 模块 — 单元测试后 **人工硬闸门**

**Files:**
- Create: `src/smart_speaker/adapters/stt/openai_whisper_stt.py`
- Create: `src/smart_speaker/adapters/testing/fake_stt.py`
- Create: `tests/test_stt_unit.py`
- Create: `scripts/manual_stt_test.py`
- Modify: `.env.example`（`STT_API_KEY`, `STT_BASE_URL`, `STT_MODEL`）
- Modify: `docs/manual-gates.md`

**Interfaces:**
- Consumes: `STT.transcribe(pcm: bytes) -> str`；pcm 为完整话轮
- Produces: `OpenAIWhisperSTT`；空转写抛 `TransientError`

#### 3A — 自动化

- [ ] **Step 1: 写失败测试（mock httpx/openai）**

```python
# tests/test_stt_unit.py
import pytest
from smart_speaker.errors import TransientError
from smart_speaker.adapters.stt.openai_whisper_stt import OpenAIWhisperSTT

@pytest.mark.asyncio
async def test_transcribe_returns_text(monkeypatch):
    stt = OpenAIWhisperSTT(api_key="k", base_url="https://example.invalid/v1", model="whisper-1")

    async def fake_transcribe_file(**kwargs):
        class R:
            text = "今天中午吃了鸡蛋"
        return R()

    # 按实际 client 封装点 monkeypatch
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
```

- [ ] **Step 2: 实现 `OpenAIWhisperSTT` + `FakeSTT`，单测 PASS**

实现要点：把 pcm_s16le 包成 wav/bytes 再调 API；记录 `stt_ms` 到 logging。

- [ ] **Step 3: 写 `scripts/manual_stt_test.py`**

流程（**不依赖**完整 orchestrator）：
1. 复用已通过的 Wake：检测到唤醒 → 播 cue
2. 录音直到静音 1.2s 或 30s（可把 VAD 逻辑先放在 `orchestrator/vad.py` 并在此脚本 import；若尚未实现，本 Task Step 3a 先抽 `vad.py`）
3. 调用真实 STT
4. 终端打印：`STT_TEXT=<<...>>` 与 `STT_MS=`
5. 请用户对照是否听清自己说的中文短句

- [ ] **Step 3a（若尚无 VAD）: 实现 `orchestrator/vad.py` + `tests/test_vad.py`**

```python
# 能量阈值 + 连续静音毫秒数；纯函数，易测
def is_speech(frame: bytes, threshold: int = 500) -> bool: ...
class SilenceVAD:
    def __init__(self, silence_ms=1200, frame_ms=40): ...
    def push(self, frame: bytes) -> str:
        """returns 'continue' | 'end_utterance'"""
```

- [ ] **Step 4: 自动化**

```bash
pytest tests/test_stt_unit.py tests/test_vad.py tests/test_wake_unit.py -v
```

Expected: PASS

- [ ] **Step 5: Commit + push**

```bash
git commit -m "feat(stt): Whisper API adapter, VAD helper, manual STT script"
git push
```

#### 3B — 人工硬闸门（必须真人）

- [ ] **Step 6: 配置密钥并运行**

```bash
# .env
STT_API_KEY=...
STT_BASE_URL=https://api.openai.com/v1   # 或兼容网关
STT_MODEL=whisper-1

python scripts/manual_stt_test.py
```

**通过清单：**

1. 唤醒成功（沿用 Task 2）
2. 说出固定句：**「今天中午吃了鸡蛋」**
3. 终端 `STT_TEXT` 中文可读，且包含「鸡蛋」或同义正确识别（允许「中午/今天」小偏差）
4. 再测一句饮食句：**「记一下晚饭吃了一碗米饭」** → 转写含「米饭」
5. 故意不说话触发超时/空结果 → 看到明确错误提示（不崩溃）
6. `docs/manual-gates.md` 追加 STT PASS（含两句原文与转写原文）

- [ ] **Step 7: 用户回复：`STT 人工验收通过`**

**⛔ STOP：** 未完成 Step 6–7 前，禁止开始 Task 4。

**Task 3 完成标准：** 单测绿 + 人工两句中文转写达标 + 用户确认。

---

### Task 4: TTS（edge-tts）— 自动化为主，一次人工听感

**Files:**
- Create: `src/smart_speaker/adapters/tts/edge_tts_tts.py`
- Create: `src/smart_speaker/adapters/testing/fake_tts.py`
- Create: `tests/test_tts_unit.py`
- Create: `scripts/manual_tts_listen.py`

**Interfaces:**
- Consumes: `TTS.synthesize(text) -> bytes`（pcm_s16le 16k）
- Produces: `EdgeTTSAdapter`（内部可先 mp3 再解码为 pcm；若解码依赖重，允许临时用 `afplay` 播 mp3 **仅在 manual 脚本**，但 Protocol 仍返回 pcm——实现时用 `pydub` 或 `audioop`/第三方解码；选一种写进代码，禁止 TBD）

**解码选择（锁定）：** 使用 `edge-tts` 流式拿到 mp3 bytes，再用标准库无法解 mp3 时增加依赖 `pydub` + 系统 `ffmpeg`；若 Mac 无 ffmpeg，manual 脚本可直接播 mp3 文件做听感，同时单元测试用 FakeTTS 返回固定 pcm，真实 Edge 转换在 `tests/test_tts_unit.py` 里 mock 掉网络，只测「空文本抛错 / 非空返回 bytes」。

- [ ] **Step 1–4: TDD Fake + Edge 包装 + pytest PASS + commit push**

- [ ] **Step 5: 人工听感（非硬闸门，但建议）**

```bash
python scripts/manual_tts_listen.py --text "已记录两个鸡蛋"
```

通过：能听清中文。失败不阻塞 Task 5，但必须开 issue 记录。

**Task 4 完成标准：** `pytest tests/test_tts_unit.py -v` PASS。

---

### Task 5: LLM（DeepSeek）+ ToolBackend（MCP 白名单）

**Files:**
- Create: `src/smart_speaker/adapters/llm/deepseek_llm.py`
- Create: `src/smart_speaker/adapters/tools/mcp_health.py`
- Create: `src/smart_speaker/adapters/testing/fake_llm.py`, `fake_tools.py`
- Create: `tests/test_llm_unit.py`, `tests/test_mcp_whitelist.py`
- Modify: `.env.example`（`DEEPSEEK_API_KEY`, `MCP_HEALTH_COMMAND`）

**Interfaces:**
- Consumes: `LLM.chat` / `ToolBackend.list_tools`+`call`
- Produces: 白名单过滤；未知工具名 → 返回错误字符串给模型，不抛崩

WHITELIST 常量：

```python
DIET_TOOL_WHITELIST = frozenset({
    "log_food", "list_foods", "add_food", "get_day", "get_daily_summary",
    "get_goals", "get_trend", "update_entry", "delete_entry",
})
```

- [ ] **Step 1: `test_mcp_whitelist.py` — 不在白名单的工具不会出现在 `list_tools`**

- [ ] **Step 2: 实现 `McpHealthToolBackend`：stdio spawn `MCP_HEALTH_COMMAND`；退出清理子进程**

- [ ] **Step 3: `test_llm_unit.py` — mock DeepSeek 返回 tool_calls 与 final_text 两种 `LLMResult`**

- [ ] **Step 4: 实现 `DeepSeekLLM`**

- [ ] **Step 5: 可选脚本 `scripts/manual_mcp_log_food.py`（文本参数，不语音）验证真 MCP 写入**

```bash
python scripts/manual_mcp_log_food.py --name 鸡蛋 --pieces 2 --meal 午
# 再用 get_day 打印核对
```

此步若 MCP 命令未配置，可先跳过真连，但单元测试必须绿。

- [ ] **Step 6: pytest 全绿 + commit + push**

**Task 5 完成标准：** `pytest tests/test_llm_unit.py tests/test_mcp_whitelist.py -v` PASS；若本机有 MCP，manual 写入核对成功。

---

### Task 6: Orchestrator 状态机（全 Fake，无硬件）

**Files:**
- Create: `src/smart_speaker/orchestrator/state_machine.py`, `session.py`
- Create: `tests/test_state_machine.py`, `tests/test_session.py`, `tests/test_orchestrator_no_cloud_imports.py`

**Interfaces:**
- Consumes: 六大 Protocol + VAD + AppConfig
- Produces: `Orchestrator.run_forever()` / 可测试的 `handle_event`

状态：`Idle → Listening → Thinking → Speaking → Idle`

- [ ] **Step 1: 写 `test_session.py` — 只保留 8 条；tool result 截断 2k**

- [ ] **Step 2: 写 `test_state_machine.py`（关键路径）**

```python
@pytest.mark.asyncio
async def test_wake_listen_think_speak_with_fakes():
    """Inject wake → pcm utterance → FakeSTT text → FakeLLM final → FakeTTS pcm played."""
    ...
    assert audio.played  # cue + reply
    assert "鸡蛋" in stt.last_input_or_text
```

覆盖：
- 正常闭环
- STT `TransientError` → 口述「没听清」
- tool 失败 → 「记录服务暂时不可用。」
- max 5 tool rounds
- Speaking 期间 capture disabled

- [ ] **Step 3: 实现状态机至测试全绿**

- [ ] **Step 4: `test_orchestrator_no_cloud_imports.py`**

```python
import ast
from pathlib import Path

FORBIDDEN = {"openai", "edge_tts", "mcp", "openwakeword", "sounddevice"}

def test_orchestrator_has_no_forbidden_imports():
    root = Path("src/smart_speaker/orchestrator")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in FORBIDDEN
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in FORBIDDEN
```

- [ ] **Step 5: Commit + push**

**Task 6 完成标准：** 上述测试全绿；无硬件。

---

### Task 7: CLI 接线 + 端到端人工（全链路）

**Files:**
- Create: `src/smart_speaker/cli.py`
- Modify: `README.md`（Mac 运行、Pi 备注、闸门说明）
- Modify: `docs/manual-gates.md`（E2E 段）

**前提：** Task 2、Task 3 人工闸门已通过。

- [ ] **Step 1: 实现 `cli.py` — 组装真实 adapters，跑 orchestrator**

```bash
smart-speaker   # 或 python -m smart_speaker
```

- [ ] **Step 2: 回归自动化**

```bash
pytest -v
```

Expected: 全绿

- [ ] **Step 3: 端到端人工场景（厨房脚本）**

1. `hey jarvis` → 提示音  
2. 「记一下午饭吃了两个鸡蛋」→ 口头确认已记录  
3. 「今天还剩多少卡」→ 数字来自 MCP 而非瞎编  
4. 「今晚怎么吃比较好」→ 建议引用今日摘要  
5. 在 `docs/manual-gates.md` 记录 E2E PASS

- [ ] **Step 4: Commit + push**

```bash
git commit -m "feat: wire CLI end-to-end diet voice loop"
git push
```

**Task 7 完成标准：** E2E 四步人工通过；README 可复现。

---

### Task 8: Linux / Pi 适配备注（文档 + 导入卫生）

**Files:**
- Modify: `README.md`（aarch64、portaudio、ffmpeg）
- Create: `docs/pi-port.md`

- [ ] **Step 1: 确认无 `AppKit` / macOS-only API（rg 扫描）**

```bash
rg -n "AppKit|AVFoundation|import objc" src || true
```

Expected: 无匹配

- [ ] **Step 2: 写 Pi 移植清单（依赖、麦克风权限、性能：LLM 仍云端）**

- [ ] **Step 3: Commit + push**

**Task 8 完成标准：** 文档齐全；扫描无 macOS-only。

---

## Execution Order (checklist for agents)

```text
Task 0 ──► Task 1 ──► Task 2 (+ 人工唤醒) ──⛔──► Task 3 (+ 人工 STT) ──⛔──► Task 4 ──► Task 5 ──► Task 6 ──► Task 7 ──► Task 8
```

每箭头处：`pytest`（相关）必须绿；⛔ 处额外需要用户中文确认句。

---

## Self-Review (writing-plans)

**1. Spec coverage**
- 唤醒 / STT / TTS / LLM / MCP / 状态机 / 半双工 / 白名单 / 私有 Git / Linux → 均有 Task
- 饮食建议 → Task 5+7（get_daily_summary + get_goals + LLM）
- 可替换性 → Fake adapters + import 禁令测试

**2. Placeholder scan**
- TTS 解码策略已锁定（pydub/ffmpeg 或 Fake + manual mp3）
- 无 TBD 步骤

**3. Type consistency**
- Protocol 签名与设计文档一致：`process_chunk` / `transcribe` / `chat` / `synthesize` / `list_tools`+`call`

---

## Spec Reference Shortcuts

| DoD 步 | 对应 Task |
|--------|-----------|
| 0 仓库 | Task 0 |
| 1 Wake | Task 2 |
| 1.5 STT | Task 3 |
| 2–3 饮食+LLM | Task 5–7 |
| 4 TTS | Task 4+7 |
| 5–6 Linux/可替换 | Task 6 import 测试 + Task 8 |
