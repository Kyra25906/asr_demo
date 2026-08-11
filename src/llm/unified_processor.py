"""调用LLM并生成正式统一理解结果。"""

from __future__ import annotations

from src.core.unified_prompts import (
    UNIFIED_UNDERSTANDING_SYSTEM_PROMPT,
    build_unified_understanding_user_prompt,
)
from src.core.unified_understanding import (
    UnifiedUnderstandingInput,
    UnifiedUnderstandingResult,
    build_degraded_understanding,
    parse_unified_understanding,
)
from src.llm.client import LLMClient
from src.llm.processor import ProcessOutcome


class UnifiedUnderstandingProcessor:
    """负责一次模型调用、严格解析、指标记录和安全降级。"""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def understand(
        self,
        request: UnifiedUnderstandingInput,
    ) -> ProcessOutcome[UnifiedUnderstandingResult]:
        generation = None
        try:
            generation = self._client.generate_json(
                system_prompt=UNIFIED_UNDERSTANDING_SYSTEM_PROMPT,
                user_prompt=build_unified_understanding_user_prompt(request),
            )
            result = parse_unified_understanding(
                generation.content,
                expected_raw_text=request.raw_text,
                session_id=request.session_id,
                segment_id=request.segment_id,
            )
            return ProcessOutcome(
                value=result,
                degraded=False,
                error=None,
                llm_attempts=generation.attempts,
                llm_processing_seconds=generation.processing_seconds,
            )
        except Exception as error:
            attempts, seconds = self._read_metrics(generation, error)
            return ProcessOutcome(
                value=build_degraded_understanding(
                    raw_text=request.raw_text,
                    session_id=request.session_id,
                    segment_id=request.segment_id,
                    reason=f"{type(error).__name__}: {error}",
                ),
                degraded=True,
                error=f"{type(error).__name__}: {error}",
                llm_attempts=attempts,
                llm_processing_seconds=seconds,
            )

    @staticmethod
    def _read_metrics(generation, error: Exception) -> tuple[int, float]:
        if generation is not None:
            return generation.attempts, generation.processing_seconds
        return (
            int(getattr(error, "attempts", 0)),
            float(getattr(error, "processing_seconds", 0.0)),
        )
