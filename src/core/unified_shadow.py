"""把统一采用链安全地接到主流程影子观察位。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from src.asr.schemas import ASRResult
from src.core.clarification_acceptance import (
    ClarificationAction,
    ClarificationContextSnapshot,
)
from src.core.reply_coordinator import ReplyCoordinator
from src.core.unified_acceptance_bypass import (
    UnifiedAcceptanceBypass,
    UnifiedAcceptanceBypassInput,
)

if TYPE_CHECKING:
    from src.core.experiment_acceptance import AcceptedExperimentAnalysis


class ShadowObservationStatus(str, Enum):
    OBSERVED = "observed"
    FAILED = "failed"


@dataclass(frozen=True)
class ShadowObservation:
    """不含口述正文或模型原始响应的影子观察摘要。

    accepted_analysis 是可选的完整分析快照，
    供主流程在统一链路活跃时直接用于事件落盘，
    避免旧链路再次调用 LLM 产生重复分析。
    """

    request_id: str
    session_id: str
    segment_id: int
    status: ShadowObservationStatus
    destination: str | None = None
    permission: str | None = None
    acceptance_kind: str | None = None
    clarification_action: str | None = None
    missing_fields: tuple[str, ...] = ()
    follow_up_required: bool | None = None
    error_type: str | None = None
    executed: bool = False
    execution_reason: str | None = None
    accepted_analysis: (
        AcceptedExperimentAnalysis | None
    ) = None
    pending_action: ClarificationAction | None = None

    def __post_init__(self) -> None:
        if self.status == ShadowObservationStatus.OBSERVED:
            if self.destination is None or self.clarification_action is None:
                raise ValueError("成功观察必须包含目标和澄清动作。")
            if self.error_type is not None:
                raise ValueError("成功观察不能携带错误。")
        elif self.error_type is None:
            raise ValueError("失败观察必须包含错误类型。")


class UnifiedShadowObserver:
    """观察统一链路的施工单；配置执行器后可真实修改协调器。"""

    def __init__(
        self,
        bypass: UnifiedAcceptanceBypass,
    ) -> None:
        self._bypass = bypass

    def observe(
        self,
        *,
        request_id: str,
        session_id: str,
        segment_id: int,
        asr_result: ASRResult,
        reply_coordinator: ReplyCoordinator,
        recent_context: tuple[str, ...] = (),
    ) -> ShadowObservation:
        try:
            snapshot = ClarificationContextSnapshot(
                unresolved=reply_coordinator.active_clarifications(),
                current_clarification_id=(
                    reply_coordinator.current_clarification().clarification_id
                    if reply_coordinator.current_clarification() is not None
                    else None
                ),
            )
            result = self._bypass.inspect(UnifiedAcceptanceBypassInput(
                request_id=request_id,
                session_id=session_id,
                segment_id=segment_id,
                asr_result=asr_result,
                clarification_context=snapshot,
                recent_context=recent_context,
            ))
            plan = result.execution_request.plan
            accepted = result.accepted_experiment
            analysis = (
                accepted.materialize_analysis()
                if accepted is not None
                else None
            )
            missing_fields = tuple(dict.fromkeys(
                field_name
                for event in (analysis.events if analysis else ())
                for field_name in event.missing_fields
            ))

            action = result.clarification_action

            return ShadowObservation(
                request_id=request_id,
                session_id=session_id,
                segment_id=segment_id,
                status=ShadowObservationStatus.OBSERVED,
                destination=plan.destination.value,
                permission=plan.permission.value,
                acceptance_kind=(accepted.kind.value if accepted else None),
                clarification_action=result.clarification_action.action_type.value,
                missing_fields=missing_fields,
                follow_up_required=(
                    analysis.should_ask_follow_up
                    if analysis is not None
                    else None
                ),
                accepted_analysis=accepted,
                pending_action=action,
            )
        except Exception as error:
            return ShadowObservation(
                request_id=request_id,
                session_id=session_id,
                segment_id=segment_id,
                status=ShadowObservationStatus.FAILED,
                error_type=type(error).__name__,
            )
