"""把ASR文本路由为统一的意图判断结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core.intent_policy import (
    IntentDecision,
    IntentDisposition,
    IntentEvidence,
    IntentPolicyEvaluator,
)
from src.core.interaction_command import (
    InteractionCommand,
    InteractionCommandParser,
)


class CommandParser(Protocol):
    """IntentRouter依赖的最小命令解析接口。"""

    def parse(self, text: str) -> InteractionCommand: ...


@dataclass(frozen=True)
class IntentRouteResult:
    """一次文本路由的完整结果。"""

    command: InteractionCommand
    decision: IntentDecision

    def __post_init__(self) -> None:
        if self.command.command_type != self.decision.command_type:
            raise ValueError(
                "command与decision的意图类型必须一致。"
            )

    @property
    def raw_text(self) -> str:
        return self.command.raw_text

    @property
    def is_experiment_text(self) -> bool:
        return (
            self.decision.disposition
            == IntentDisposition.PASS_TO_EXPERIMENT
        )


class IntentRouter:
    """第一版只路由现有精确规则，不进行语义猜测。"""

    def __init__(
        self,
        parser: CommandParser = InteractionCommandParser,
    ) -> None:
        self._parser = parser

    def route(self, text: str) -> IntentRouteResult:
        command = self._parser.parse(text)
        decision = IntentPolicyEvaluator.evaluate(
            command.command_type,
            IntentEvidence.EXACT_RULE,
        )
        return IntentRouteResult(
            command=command,
            decision=decision,
        )
