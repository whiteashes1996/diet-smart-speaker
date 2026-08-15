"""CLI: assemble real adapters and run orchestrator."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from smart_speaker.adapters.audio.sounddevice_io import SoundDeviceAudioIO
from smart_speaker.adapters.llm.deepseek_llm import DeepSeekLLM
from smart_speaker.adapters.tools.local_notes import LocalNoteToolBackend, MultiToolBackend
from smart_speaker.adapters.tools.mcp_health import build_mcp_health_backend
from smart_speaker.adapters.tts.piper_tts import PiperTTS
from smart_speaker.adapters.wake.openwakeword_wake import OpenWakeWordWake
from smart_speaker.config import load_config
from smart_speaker.errors import FatalError
from smart_speaker.orchestrator.state_machine import Orchestrator, load_wake_cue_pcm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("smart_speaker")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _build_stt(cfg):
    """Prefer local SenseVoice on Pi; fall back to OpenAI Whisper if key provided."""
    try:
        from smart_speaker.adapters.stt.sensevoice_stt import SenseVoiceSTT

        return SenseVoiceSTT(
            model_path=cfg.sensevoice_model,
            tokens_path=cfg.sensevoice_tokens,
            sample_rate=cfg.sample_rate,
        )
    except FatalError:
        if cfg.stt_api_key:
            from smart_speaker.adapters.stt.openai_whisper_stt import OpenAIWhisperSTT

            return OpenAIWhisperSTT(
                api_key=cfg.stt_api_key,
                base_url=cfg.stt_base_url or "https://api.openai.com/v1",
                model=cfg.stt_model,
                sample_rate=cfg.sample_rate,
            )
        raise


async def _async_main() -> int:
    cfg = load_config()
    if not cfg.deepseek_api_key:
        print("Missing config: DEEPSEEK_API_KEY", file=sys.stderr)
        return 1

    cue_path = _repo_root() / "assets" / "wake_cue.wav"
    cue = load_wake_cue_pcm(cue_path) if cue_path.is_file() else b"\x00\x00" * 800

    # Local notes always available; health MCP optional (HTTP URL or stdio).
    notes = LocalNoteToolBackend(memory_dir=cfg.memory_dir)
    backends = [notes]
    health = build_mcp_health_backend(cfg)
    if health is not None:
        await health.connect()
        await health.refresh_tools()
        backends.insert(0, health)
    tools = MultiToolBackend(backends)

    audio = SoundDeviceAudioIO(cfg)
    wake = OpenWakeWordWake(
        model_name=cfg.wake_word,
        threshold=cfg.wake_threshold,
        refractory_s=cfg.wake_refractory_s,
    )
    stt = _build_stt(cfg)
    llm = DeepSeekLLM(api_key=cfg.deepseek_api_key)
    tts = PiperTTS(
        piper_bin=cfg.piper_bin,
        model_path=cfg.piper_model,
        sample_rate=cfg.sample_rate,
    )

    orch = Orchestrator(
        config=cfg,
        audio=audio,
        wake=wake,
        stt=stt,
        llm=llm,
        tts=tts,
        tools=tools,
        wake_cue_pcm=cue,
        conversation_idle_s=cfg.conversation_idle_s,
    )
    logger.info(
        "smart-speaker running — say %s (conversation idle %.1fs)",
        cfg.wake_word,
        cfg.conversation_idle_s,
    )
    try:
        await orch.run_forever()
    except KeyboardInterrupt:
        orch.request_stop()
    finally:
        if health is not None:
            await health.close()
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_async_main()))
    except FatalError as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
