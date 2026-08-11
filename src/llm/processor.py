from dataclasses import dataclass
from typing import Generic, TypeVar

from .client import (
    LLMClient,
    LLMGenerationResult,
)
from .prompts import (
    ANALYSIS_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_analysis_user_prompt,
    build_summary_user_prompt,
)
from .schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    ExperimentSummary,
    LLMAnalysisResult,
)
from .validation import (
    parse_analysis,
    parse_summary,
)


T = TypeVar("T")


@dataclass(frozen=True)
class ProcessOutcome(
    Generic[T]
):
    """
    一次LLM业务处理的完整结果。

    llm_attempts和llm_processing_seconds
    属于运行元数据，不属于实验事实。
    """

    value: T
    degraded: bool = False
    error: str | None = None
    llm_attempts: int = 0
    llm_processing_seconds: float = 0.0


class ExperimentLLMProcessor:
    """
    封装提示词、模型调用、
    严格校验和保真降级。
    """

    def __init__(
        self,
        client: LLMClient,
    ) -> None:
        self.client = client

    def analyze_segment(
        self,
        *,
        raw_text: str,
        session_id: str,
        segment_id: int,
        context: tuple[str, ...] = (),
    ) -> ProcessOutcome[
        LLMAnalysisResult
    ]:
        generation = None

        try:
            if not raw_text.strip():
                raise ValueError(
                    "ASR原文为空"
                )

            generation = (
                self.client.generate_json(
                    system_prompt=(
                        ANALYSIS_SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        build_analysis_user_prompt(
                            raw_text,
                            context,
                        )
                    ),
                )
            )

            result = parse_analysis(
                generation.content,
                expected_raw_text=raw_text,
                session_id=session_id,
                segment_id=segment_id,
            )

            return ProcessOutcome(
                value=result,
                degraded=False,
                error=None,
                llm_attempts=(
                    generation.attempts
                ),
                llm_processing_seconds=(
                    generation
                    .processing_seconds
                ),
            )

        except Exception as error:
            attempts, seconds = (
                self._read_metrics(
                    generation=generation,
                    error=error,
                )
            )

            return ProcessOutcome(
                value=self._fallback_analysis(
                    raw_text,
                    session_id,
                    segment_id,
                ),
                degraded=True,
                error=(
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                llm_attempts=attempts,
                llm_processing_seconds=(
                    seconds
                ),
            )

    def summarize(
        self,
        event_records: list[dict],
        *,
        scope: str,
    ) -> ProcessOutcome[
        ExperimentSummary
    ]:
        generation = None

        try:
            generation = (
                self.client.generate_json(
                    system_prompt=(
                        SUMMARY_SYSTEM_PROMPT
                    ),
                    user_prompt=(
                        build_summary_user_prompt(
                            event_records,
                            scope=scope,
                        )
                    ),
                )
            )

            summary = parse_summary(
                generation.content
            )

            return ProcessOutcome(
                value=summary,
                degraded=False,
                error=None,
                llm_attempts=(
                    generation.attempts
                ),
                llm_processing_seconds=(
                    generation
                    .processing_seconds
                ),
            )

        except Exception as error:
            attempts, seconds = (
                self._read_metrics(
                    generation=generation,
                    error=error,
                )
            )

            fallback = ExperimentSummary(
                summary=(
                    "总结暂时不可用，"
                    "完整结构化事件已保留。"
                ),
                unresolved_questions=[
                    "模型总结失败，"
                    "请稍后重试。"
                ],
            )

            return ProcessOutcome(
                value=fallback,
                degraded=True,
                error=(
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                llm_attempts=attempts,
                llm_processing_seconds=(
                    seconds
                ),
            )

    @staticmethod
    def _read_metrics(
        *,
        generation: (
            LLMGenerationResult
            | None
        ),
        error: Exception,
    ) -> tuple[int, float]:
        """
        优先从成功的客户端结果读取指标。

        如果客户端失败，则从
        LLMClientError的属性读取。
        普通本地校验错误没有客户端指标时，
        使用0作为默认值。
        """

        if generation is not None:
            return (
                generation.attempts,
                generation.processing_seconds,
            )

        attempts = getattr(
            error,
            "attempts",
            0,
        )

        seconds = getattr(
            error,
            "processing_seconds",
            0.0,
        )

        return (
            int(attempts),
            float(seconds),
        )

    @staticmethod
    def _fallback_analysis(
        raw_text: str,
        session_id: str,
        segment_id: int,
    ) -> LLMAnalysisResult:
        event = ExperimentEvent(
            event_type=(
                ExperimentEventType.NOTE
            ),
            raw_text=raw_text,
            normalized_text=raw_text,
            entities=(
                ExperimentEntities()
            ),
            needs_confirmation=True,
            confirmation_reason=(
                "模型处理失败，"
                "仅保留未经解释的"
                "ASR原文。"
            ),
            source_session_id=(
                session_id
            ),
            source_segment_id=(
                segment_id
            ),
        )

        return LLMAnalysisResult(
            events=[event],
            should_ask_follow_up=False,
            follow_up_question=None,
            assistant_reply=None,
        )