"""用固定非敏感WAV验收真实ASR到安全分派的无副作用旁路。"""

from __future__ import annotations

import json
from pathlib import Path

from src.asr.factory import create_asr_backend
from src.config import LLM_MODEL, TEST_AUDIO
from src.core.unified_dispatch_bypass import (
    UnifiedDispatchBypass,
    UnifiedDispatchBypassInput,
)
from src.llm.factory import create_llm_client
from src.llm.unified_processor import UnifiedUnderstandingProcessor
from src.llm.unified_router import UnifiedUnderstandingRouter


REAL_BYPASS_SESSION_ID = "unified_dispatch_wav_real"
SAFE_REPORT_FIELDS = frozenset({
    "audio_fixture",
    "asr_backend_model",
    "audio_duration_seconds",
    "recognition_seconds",
    "asr_transcript",
    "route_source",
    "intent_evidence",
    "intent_type",
    "intent_risk",
    "intent_disposition",
    "destination",
    "permission",
    "degraded",
    "llm_attempts",
    "llm_processing_seconds",
    "reason",
})


def build_safe_observation(
    *,
    asr_backend,
    processor,
    audio_path: Path = TEST_AUDIO,
) -> dict:
    """运行旁路并返回不含模型原文、绝对路径或原始响应的摘要。"""

    fixed_audio = Path(audio_path)
    if not fixed_audio.is_file():
        raise FileNotFoundError(f"固定WAV不存在：{fixed_audio.name}")

    asr_result = asr_backend.recognize(fixed_audio)
    bypass = UnifiedDispatchBypass(
        UnifiedUnderstandingRouter(processor)
    )
    observation = bypass.inspect(UnifiedDispatchBypassInput(
        asr_result=asr_result,
        session_active=True,
        session_id=REAL_BYPASS_SESSION_ID,
        segment_id=1,
    ))

    report = observation.to_dict()
    report.update({
        "audio_fixture": fixed_audio.name,
        "asr_backend_model": asr_result.model,
        "audio_duration_seconds": asr_result.audio_duration_seconds,
        "recognition_seconds": asr_result.recognition_seconds,
    })
    if set(report) != SAFE_REPORT_FIELDS:
        raise RuntimeError("旁路观察报告字段与脱敏白名单不一致。")
    return report


def main() -> None:
    print("固定WAV真实统一分派旁路验收")
    print(f"统一理解模型：{LLM_MODEL}")
    print("原始模型文本/响应：不打印、不保存")
    print("存储、状态机、ReplyCoordinator、TTS：未连接")

    report = build_safe_observation(
        asr_backend=create_asr_backend(),
        processor=UnifiedUnderstandingProcessor(create_llm_client()),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
