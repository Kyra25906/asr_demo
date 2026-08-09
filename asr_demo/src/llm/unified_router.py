"""组合精确命令快速路径与正式统一理解Processor。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core.intent_policy import (
    IntentDecision,
    IntentEvidence,
    IntentPolicyEvaluator,
)
from src.core.interaction_command import (
    InteractionCommand,
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.unified_understanding import (
    UnifiedUnderstandingInput,
    UnifiedUnderstandingResult,
)
from src.llm.processor import ProcessOutcome


class UnderstandingProcessor(Protocol):
    """统一路由器依赖的最小理解接口。"""

    def understand(
        self,
        request: UnifiedUnderstandingInput,
    ) -> ProcessOutcome[UnifiedUnderstandingResult]: ...


@dataclass(frozen=True)
class UnifiedRouteResult:
    """精确路径或统一理解路径产生的模块级路由结果。"""

    decision: IntentDecision
    exact_command: InteractionCommand | None = None
    understanding_outcome: (
        ProcessOutcome[UnifiedUnderstandingResult] | None
    ) = None

    def __post_init__(self) -> None:
        selected = sum(
            value is not None
            for value in (self.exact_command, self.understanding_outcome)
        )
        if selected != 1:
            raise ValueError("路由结果必须且只能来自一条处理路径。")
        if (
            self.exact_command is not None
            and self.exact_command.command_type != self.decision.command_type
        ):
            raise ValueError("精确命令与风险决策的类型必须一致。")

    @property
    def llm_used(self) -> bool:
        return self.understanding_outcome is not None

    @property
    def raw_text(self) -> str:
        if self.exact_command is not None:
            return self.exact_command.raw_text
        return self.understanding_outcome.value.raw_text


class UnifiedUnderstandingRouter:
    """精确控制命令本地处理，其他文本统一调用一次LLM。"""

    def __init__(
        self,
        processor: UnderstandingProcessor,
        parser=InteractionCommandParser,
    ) -> None:
        self._processor = processor
        self._parser = parser

    def route(
        self,
        request: UnifiedUnderstandingInput,
    ) -> UnifiedRouteResult:
        exact_command = self._parser.parse(request.raw_text)
        if exact_command.is_control_candidate:
            return UnifiedRouteResult(
                exact_command=exact_command,
                decision=IntentPolicyEvaluator.evaluate(
                    exact_command.command_type,
                    IntentEvidence.EXACT_RULE,
                ),
            )

        outcome = self._processor.understand(request)
        understanding = outcome.value
        if understanding.control is not None:
            command_type = understanding.control.intent.command_type
            if command_type is None:
                raise ValueError("control理解结果缺少命令类型。")
        else:
            command_type = InteractionCommandType.NORMAL

        return UnifiedRouteResult(
            understanding_outcome=outcome,
            decision=IntentPolicyEvaluator.evaluate(
                command_type,
                IntentEvidence.LLM_CANDIDATE,
            ),
        )
