"""运行五类固定文本的统一路由安全分派旁路，不执行任何动作。"""

from __future__ import annotations

import json

from src.asr.schemas import ASRResult
from src.core.intent_classifier import IntentCandidate
from src.core.interaction_command import InteractionCommandType
from src.core.unified_dispatch_bypass import (
    UnifiedDispatchBypass,
    UnifiedDispatchBypassInput,
)
from src.core.unified_understanding import (
    ControlUnderstanding,
    ExperimentUnderstanding,
    UnifiedUnderstandingResult,
    UncertainUnderstanding,
    build_degraded_understanding,
)
from src.llm.processor import ProcessOutcome
from src.llm.schemas import LLMAnalysisResult
from src.llm.unified_router import UnifiedUnderstandingRouter


FIXED_TEXTS = (
    "加入五毫升缓冲液。",
    "查看待确认问题。",
    "今天先记录到这里吧。",
    "这个差不多了。",
    "模拟统一理解失败。",
)


class FixedFakeProcessor:
    """只为旁路连线验收提供确定性理解结果。"""

    def understand(self, request):
        raw_text = request.raw_text
        if raw_text == FIXED_TEXTS[0]:
            result = UnifiedUnderstandingResult(
                raw_text=raw_text,
                experiment=ExperimentUnderstanding(
                    LLMAnalysisResult(events=[])
                ),
            )
            return ProcessOutcome(value=result)
        if raw_text == FIXED_TEXTS[2]:
            result = UnifiedUnderstandingResult(
                raw_text=raw_text,
                control=ControlUnderstanding(IntentCandidate(
                    command_type=InteractionCommandType.END_SESSION,
                    reason="Fake自然结束候选。",
                )),
            )
            return ProcessOutcome(value=result)
        if raw_text == FIXED_TEXTS[3]:
            result = UnifiedUnderstandingResult(
                raw_text=raw_text,
                uncertain=UncertainUnderstanding("Fake证据不足。"),
            )
            return ProcessOutcome(value=result)
        if raw_text == FIXED_TEXTS[4]:
            result = build_degraded_understanding(
                raw_text=raw_text,
                session_id=request.session_id,
                segment_id=request.segment_id,
                reason="Fake timeout",
            )
            return ProcessOutcome(
                value=result,
                degraded=True,
                error="Fake timeout",
                llm_attempts=2,
                llm_processing_seconds=0.3,
            )
        raise AssertionError(f"未配置的Fake文本：{raw_text}")


def build_fixed_observations() -> list[dict]:
    bypass = UnifiedDispatchBypass(
        UnifiedUnderstandingRouter(FixedFakeProcessor())
    )
    observations = []
    for segment_id, text in enumerate(FIXED_TEXTS, start=1):
        asr_result = ASRResult(
            asr_transcript=text,
            asr_model_raw_text=f"<|zh|>{text}",
            audio_path=f"fixed://segment-{segment_id}",
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fixed-fake-asr",
            language="zh",
        )
        observation = bypass.inspect(UnifiedDispatchBypassInput(
            asr_result=asr_result,
            session_active=True,
            session_id="bypass-session",
            segment_id=segment_id,
            pending_question_numbers=(1, 2),
            current_question_number=1,
        ))
        observations.append(observation.to_dict())
    return observations


def main() -> None:
    print(json.dumps(
        build_fixed_observations(),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
