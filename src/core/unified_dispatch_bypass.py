"""ASR证据到安全分派计划的无副作用旁路。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.asr.schemas import ASRResult
from src.core.unified_dispatch import (
    UnifiedDispatchPlan,
    UnifiedDispatchPlanner,
)
from src.core.unified_understanding import UnifiedUnderstandingInput
from src.llm.unified_router import UnifiedRouteResult


class UnifiedRouter(Protocol):
    def route(
        self,
        request: UnifiedUnderstandingInput,
    ) -> UnifiedRouteResult: ...


@dataclass(frozen=True)
class UnifiedDispatchBypassInput:
    """旁路所需的可信ASR证据与只读会话上下文。"""

    asr_result: ASRResult
    session_active: bool
    session_id: str
    segment_id: int
    recent_context: tuple[str, ...] = ()
    pending_question_numbers: tuple[int, ...] = ()
    current_question_number: int | None = None

    def __post_init__(self) -> None:
        if not self.asr_result.is_final:
            raise ValueError("旁路只接受最终ASR结果。")

    def to_understanding_input(self) -> UnifiedUnderstandingInput:
        """只转发忠实转写，不转发ASR模型标签文本。"""

        return UnifiedUnderstandingInput(
            raw_text=self.asr_result.asr_transcript,
            session_active=self.session_active,
            session_id=self.session_id,
            segment_id=self.segment_id,
            recent_context=self.recent_context,
            pending_question_numbers=(
                self.pending_question_numbers
            ),
            current_question_number=(
                self.current_question_number
            ),
        )


@dataclass(frozen=True)
class UnifiedDispatchObservation:
    """可观察旁路结果；只描述计划，不提供执行方法。"""

    plan: UnifiedDispatchPlan

    def to_dict(self) -> dict[str, Any]:
        route = self.plan.route_result
        outcome = route.understanding_outcome
        return {
            "asr_transcript": self.plan.asr_transcript,
            "route_source": (
                "unified_understanding"
                if route.llm_used
                else "exact_rule"
            ),
            "intent_evidence": route.decision.evidence.value,
            "intent_type": route.decision.command_type.value,
            "intent_risk": route.decision.risk.value,
            "intent_disposition": (
                route.decision.disposition.value
            ),
            "destination": self.plan.destination.value,
            "permission": self.plan.permission.value,
            "degraded": bool(
                outcome is not None and outcome.degraded
            ),
            "llm_attempts": (
                outcome.llm_attempts
                if outcome is not None
                else 0
            ),
            "llm_processing_seconds": (
                outcome.llm_processing_seconds
                if outcome is not None
                else 0.0
            ),
            "reason": self.plan.reason,
        }


class UnifiedDispatchBypass:
    """只连接Router与Planner，不依赖任何执行型服务。"""

    def __init__(self, router: UnifiedRouter) -> None:
        self._router = router

    def inspect(
        self,
        bypass_input: UnifiedDispatchBypassInput,
    ) -> UnifiedDispatchObservation:
        request = bypass_input.to_understanding_input()
        route_result = self._router.route(request)
        if route_result.raw_text != bypass_input.asr_result.asr_transcript:
            raise ValueError("Router没有原样保留ASR忠实转写。")
        plan = UnifiedDispatchPlanner.plan(route_result)
        return UnifiedDispatchObservation(plan=plan)
