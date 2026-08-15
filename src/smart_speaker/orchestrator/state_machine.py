"""Voice orchestrator state machine (protocol-only dependencies)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from smart_speaker.config import AppConfig
from smart_speaker.errors import TransientError
from smart_speaker.orchestrator.session import Session
from smart_speaker.orchestrator.vad import SilenceVAD
from smart_speaker.protocols.llm import LLMResult

logger = logging.getLogger(__name__)

PROMPT_WAKE = "我在"
PROMPT_STT_FAIL = "没听清，请再说一次。"
PROMPT_NET_FAIL = "网络有点问题，稍后再试。"
PROMPT_MCP_FAIL = "记录服务暂时不可用。"
PROMPT_MIC_FAIL = "没有麦克风权限。"
PROMPT_END = "好的，结束对话。"

# 结束会话关键词（识别文本包含任一即退出多轮对话）
END_CONVERSATION_KEYWORDS = (
    "结束对话",
    "退出对话",
    "关闭对话",
    "再见",
    "拜拜",
    "拜",
    "不用了",
    "没事了",
    "就这样吧",
    "结束吧",
)

SYSTEM_PROMPT = """你是厨房里的饮食语音助手。回复必须尽量短、口语化，方便语音播报。
默认一两句话，不超过 30 个字；不要解释、不要列要点、不要寒暄。
记饮食时调用工具：餐次映射 早饭→早、午饭→午、晚饭→晚、加餐→加、夜宵→夜。
缺重量可合理默认或追问。给建议前先用 get_daily_summary 和 get_goals，必须引用工具返回的数字。
时区 Asia/Shanghai，日期缺省为当天；调用工具时“今天”必须用系统给出的日期，不要自己猜。

本地记忆工具：
- 用户说“记住/记下来/提醒我/保存”时，调用 save_note 保存到本地。
- 用户问“我之前说过/上次/有没有记过/我记过什么”时，先调用 search_notes 检索，
  再根据返回内容回答；不要凭空编造历史。
"""


class State(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class Orchestrator:
    def __init__(
        self,
        config: AppConfig,
        audio: Any,
        wake: Any,
        stt: Any,
        llm: Any,
        tts: Any,
        tools: Any,
        wake_cue_pcm: bytes | None = None,
        frame_ms: int = 40,
        max_tool_rounds: int = 5,
        thinking_timeout_s: float = 45.0,
        conversation_idle_s: float | None = None,
    ) -> None:
        self.config = config
        self.audio = audio
        self.wake = wake
        self.stt = stt
        self.llm = llm
        self.tts = tts
        self.tools = tools
        self.wake_cue_pcm = wake_cue_pcm or b"\x00\x00" * 800
        self.frame_ms = frame_ms
        self.max_tool_rounds = max_tool_rounds
        self.thinking_timeout_s = thinking_timeout_s
        self.conversation_idle_s = (
            conversation_idle_s
            if conversation_idle_s is not None
            else float(getattr(config, "conversation_idle_s", 3.0))
        )
        self.state = State.IDLE
        self.session = Session()
        self._utterance = bytearray()
        self._vad = SilenceVAD(
            silence_ms=config.silence_ms,
            frame_ms=frame_ms,
            threshold=int(getattr(config, "vad_threshold", 1500)),
        )
        self._listen_started = 0.0
        self._stop = False
        self._chunk_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._in_conversation = False
        self._last_activity = 0.0

    def request_stop(self) -> None:
        self._stop = True

    def _on_chunk(self, pcm: bytes) -> None:
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self._chunk_queue.put_nowait, pcm)

    async def run_forever(self) -> None:
        self._loop = asyncio.get_running_loop()
        self.audio.start_input(self._on_chunk)
        try:
            while not self._stop:
                chunk = await self._chunk_queue.get()
                if chunk is None:
                    break
                await self._handle_chunk(chunk)
        finally:
            self.audio.stop_input()

    async def run_turn_from_pcm(self, utterance_pcm: bytes, user_text_override: str | None = None) -> str:
        """Test helper: skip wake/listen, run thinking+speaking; returns spoken text."""
        self.state = State.THINKING
        if user_text_override is not None:
            text = user_text_override
        else:
            try:
                text = await self.stt.transcribe(utterance_pcm)
            except TransientError:
                await self._speak(PROMPT_STT_FAIL)
            if self._in_conversation:
                self._exit_conversation()
            self.state = State.IDLE
            return PROMPT_STT_FAIL
        reply = await self._think(text)
        await self._speak(reply)
        if self._in_conversation:
            self._exit_conversation()
        self.state = State.IDLE
        return reply

    async def simulate_wake_and_utterance(self, utterance_pcm: bytes) -> str:
        """Fake path: wake ack → listen buffer already provided → think → speak."""
        await self._speak(PROMPT_WAKE)
        self.state = State.LISTENING
        self._utterance = bytearray(utterance_pcm)
        self.state = State.THINKING
        try:
            text = await self.stt.transcribe(bytes(self._utterance))
        except TransientError:
            await self._speak(PROMPT_STT_FAIL)
            if self._in_conversation:
                self._exit_conversation()
            self.state = State.IDLE
            return PROMPT_STT_FAIL
        reply = await self._think(text)
        await self._speak(reply)
        if self._in_conversation:
            self._exit_conversation()
        self.state = State.IDLE
        return reply

    def _enter_conversation(self) -> None:
        self._in_conversation = True
        self._last_activity = time.monotonic()

    def _exit_conversation(self) -> None:
        self._in_conversation = False
        self.session = Session()

    def _system_prompt(self) -> str:
        tz = getattr(self.config, "timezone", "Asia/Shanghai") or "Asia/Shanghai"
        today = datetime.now(ZoneInfo(tz)).date().isoformat()
        return f"{SYSTEM_PROMPT}\n今天日期是 {today}。"

    def _is_too_short(self, text: str) -> bool:
        cleaned = "".join(text.split())
        return len(cleaned) < int(getattr(self.config, "min_transcript_chars", 2))

    @staticmethod
    def _is_end_conversation(text: str) -> bool:
        t = text.strip().lower()
        if not t:
            return False
        return any(kw.lower() in t for kw in END_CONVERSATION_KEYWORDS)

    def _reset_listen(self) -> None:
        self.state = State.LISTENING
        self._utterance.clear()
        self._vad.reset()
        self._listen_started = time.monotonic()

    async def _handle_chunk(self, pcm: bytes) -> None:
        if self.state == State.IDLE:
            if self.wake.process_chunk(pcm):
                logger.info("wake detected")
                self._enter_conversation()
                await self._speak(PROMPT_WAKE)
                self._reset_listen()
                self.audio.set_capture_enabled(True)
            return

        if self.state == State.LISTENING:
            # In conversation mode, treat silence as end of utterance; if no speech
            # at all for a while, drop back to wake word.
            if self._in_conversation:
                if self._vad.is_speech_frame(pcm):
                    self._last_activity = time.monotonic()
            self._utterance.extend(pcm)
            elapsed = time.monotonic() - self._listen_started
            if elapsed >= self.config.max_listen_s:
                await self._finish_listening()
                return
            if self._vad.push(pcm) == "end_utterance":
                await self._finish_listening()
                return
            if (
                self._in_conversation
                and not self._vad.heard_speech
                and elapsed >= self.conversation_idle_s
            ):
                logger.info("conversation idle for %.1fs, back to wake", elapsed)
                self._utterance.clear()
                self._exit_conversation()
                self.state = State.IDLE
            return

        # THINKING / SPEAKING: ignore mic (half-duplex)
        return

    def _back_to_listen(self) -> None:
        self._reset_listen()
        self.audio.set_capture_enabled(True)

    async def _finish_listening(self) -> None:
        self.state = State.THINKING
        self.audio.set_capture_enabled(False)
        pcm = bytes(self._utterance)
        self._utterance.clear()
        try:
            text = await self.stt.transcribe(pcm)
        except TransientError:
            await self._speak(PROMPT_STT_FAIL)
            if self._in_conversation:
                self._back_to_listen()
            else:
                self.state = State.IDLE
                self.audio.set_capture_enabled(True)
            return
        if not text.strip():
            await self._speak(PROMPT_STT_FAIL)
            if self._in_conversation:
                self._back_to_listen()
            else:
                self.state = State.IDLE
                self.audio.set_capture_enabled(True)
            return
        if self._in_conversation and self._is_end_conversation(text):
            logger.info("end-conversation keyword: %s", text)
            await self._speak(PROMPT_END)
            self._exit_conversation()
            self.state = State.IDLE
            self.audio.set_capture_enabled(True)
            return
        if self._is_too_short(text):
            logger.info("transcript too short, skip LLM: %s", text)
            if self._in_conversation:
                self._back_to_listen()
            else:
                self.state = State.IDLE
                self.audio.set_capture_enabled(True)
            return
        try:
            reply = await asyncio.wait_for(self._think(text), timeout=self.thinking_timeout_s)
        except TimeoutError:
            reply = PROMPT_NET_FAIL
        except TransientError:
            reply = PROMPT_NET_FAIL
        await self._speak(reply)
        self._last_activity = time.monotonic()
        if self._in_conversation:
            self._back_to_listen()
        else:
            self.state = State.IDLE
            self.audio.set_capture_enabled(True)

    def _openai_tools(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for spec in self.tools.list_tools():
            out.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec.name,
                        "description": spec.description,
                        "parameters": spec.parameters or {"type": "object", "properties": {}},
                    },
                }
            )
        return out

    async def _think(self, user_text: str) -> str:
        self.session.add_user(user_text)
        messages: list[dict[str, Any]] = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(self.session.messages)
        tools = self._openai_tools()
        for _ in range(self.max_tool_rounds):
            try:
                result: LLMResult = await self.llm.chat(messages, tools)
            except TransientError:
                return PROMPT_NET_FAIL
            if result.tool_calls:
                # record assistant tool call message for APIs that need it
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": __import__("json").dumps(tc.arguments),
                                },
                            }
                            for tc in result.tool_calls
                        ],
                    }
                )
                for tc in result.tool_calls:
                    try:
                        tool_out = await self.tools.call(tc.name, tc.arguments)
                    except Exception:  # noqa: BLE001
                        tool_out = PROMPT_MCP_FAIL
                        self.session.add_assistant(PROMPT_MCP_FAIL)
                        return PROMPT_MCP_FAIL
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": tool_out,
                        }
                    )
                    self.session.add_tool_result(tc.id, tc.name, tool_out)
                continue
            text = (result.final_text or "").strip() or PROMPT_NET_FAIL
            self.session.add_assistant(text)
            return text
        return "这次步骤有点多，请再说一次你的需求。"

    async def _speak(self, text: str) -> None:
        self.state = State.SPEAKING
        self.audio.set_capture_enabled(False)
        try:
            pcm = await self.tts.synthesize(text)
            self.audio.play(pcm)
        except TransientError:
            # best-effort: nothing to play
            logger.warning("TTS failed for: %s", text[:40])
        finally:
            self.audio.set_capture_enabled(True)


def load_wake_cue_pcm(path: Path) -> bytes:
    import wave

    with wave.open(str(path), "rb") as wf:
        return wf.readframes(wf.getnframes())
