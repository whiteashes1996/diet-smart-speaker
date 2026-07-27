"""CLI: assemble real adapters and run orchestrator."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from smart_speaker.adapters.audio.sounddevice_io import SoundDeviceAudioIO
from smart_speaker.adapters.llm.deepseek_llm import DeepSeekLLM
from smart_speaker.adapters.stt.openai_whisper_stt import OpenAIWhisperSTT
from smart_speaker.adapters.tools.mcp_health import McpHealthToolBackend
from smart_speaker.adapters.tts.edge_tts_tts import EdgeTTSAdapter
from smart_speaker.adapters.wake.openwakeword_wake import OpenWakeWordWake
from smart_speaker.config import load_config
from smart_speaker.errors import FatalError
from smart_speaker.orchestrator.state_machine import Orchestrator, load_wake_cue_pcm

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("smart_speaker")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


async def _async_main() -> int:
    cfg = load_config()
    missing = []
    if not cfg.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if not cfg.stt_api_key:
        missing.append("STT_API_KEY")
    if not cfg.mcp_health_command:
        missing.append("MCP_HEALTH_COMMAND")
    if missing:
        print(f"Missing config: {', '.join(missing)}", file=sys.stderr)
        return 1

    cue_path = _repo_root() / "assets" / "wake_cue.wav"
    cue = load_wake_cue_pcm(cue_path) if cue_path.is_file() else b"\x00\x00" * 800

    tools = McpHealthToolBackend(cfg.mcp_health_command)
    await tools.connect()
    await tools.refresh_tools()

    audio = SoundDeviceAudioIO(sample_rate=cfg.sample_rate)
    wake = OpenWakeWordWake(model_name=cfg.wake_word)
    stt = OpenAIWhisperSTT(
        api_key=cfg.stt_api_key,
        base_url=cfg.stt_base_url or "https://api.openai.com/v1",
        model=cfg.stt_model,
        sample_rate=cfg.sample_rate,
    )
    llm = DeepSeekLLM(api_key=cfg.deepseek_api_key)
    tts = EdgeTTSAdapter(sample_rate=cfg.sample_rate)

    orch = Orchestrator(
        config=cfg,
        audio=audio,
        wake=wake,
        stt=stt,
        llm=llm,
        tts=tts,
        tools=tools,
        wake_cue_pcm=cue,
    )
    logger.info("smart-speaker running — say %s", cfg.wake_word)
    try:
        await orch.run_forever()
    except KeyboardInterrupt:
        orch.request_stop()
    finally:
        await tools.close()
    return 0


def main() -> None:
    try:
        raise SystemExit(asyncio.run(_async_main()))
    except FatalError as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
