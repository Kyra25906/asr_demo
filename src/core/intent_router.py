"""把ASR文本路由为统一的意图判断结果。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from src.core.intent_classifier import (
    IntentClassificationInput,
    IntentClassifier,
)
from src.core.intent_policy import (
    IntentDecision,
    IntentDisposition,
    IntentEvidence,
    IntentPolicyEvaluator,
)
from src.core.interaction_command import (
    InteractionCommand,
    InteractionCommandParser,
    InteractionCommandType,
)


class CommandParser(Protocol):
    """IntentRouter依赖的最小命令解析接口。"""

    def parse(self, text: str) -> InteractionCommand: ...


@dataclass(frozen=True)
class IntentRouteResult:
    """一次文本路由的完整结果。"""

    command: InteractionCommand
    decision: IntentDecision
    classifier_used: bool = False
    candidate_reason: str | None = None
    classification_error: str | None = None

    def __post_init__(self) -> None:
        if self.command.command_type != self.decision.command_type:
            raise ValueError(
                "command与decision的意图类型必须一致。"
            )
        if self.classification_error is not None and not self.classifier_used:
            raise ValueError(
                "未调用分类器时不能包含classification_error。"
            )
        if (
            self.candidate_reason is not None
            and self.decision.evidence != IntentEvidence.LLM_CANDIDATE
        ):
            raise ValueError(
                "只有LLM候选路由可以包含candidate_reason。"
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
        classifier: IntentClassifier | None = None,
    ) -> None:
        self._parser = parser
        self._classifier = classifier

    def route(
        self,
        text: str,
        *,
        session_active: bool = True,
        pending_question_numbers: tuple[int, ...] = (),
        current_question_number: int | None = None,
    ) -> IntentRouteResult:
        command = self._parser.parse(text)
        if (
            command.is_control_candidate
            or self._classifier is None
        ):
            return self._route_exact(command)

        request = IntentClassificationInput(
            raw_text=text,
            session_active=session_active,
            pending_question_numbers=pending_question_numbers,
            current_question_number=current_question_number,
        )
        try:
            candidate = self._classifier.classify(request)
            candidate_command = InteractionCommand(
                command_type=candidate.command_type,
                raw_text=text,
                normalized_text=InteractionCommandParser.normalize(text),
                target_question_number=(
                    candidate.target_question_number
                ),
                answer_text=candidate.answer_text,
            )
            decision = IntentPolicyEvaluator.evaluate(
                candidate.command_type,
                candidate.evidence,
            )
            return IntentRouteResult(
                command=candidate_command,
                decision=decision,
                classifier_used=True,
                candidate_reason=candidate.reason,
            )
        except Exception as error:
            # 外部分类失败不能执行任何控制动作；原文仍作为普通输入
            # 交还后续链路，并显式携带降级原因供调用方记录。
            fallback_command = InteractionCommand(
                command_type=InteractionCommandType.NORMAL,
                raw_text=text,
                normalized_text=InteractionCommandParser.normalize(text),
            )
            fallback_decision = IntentPolicyEvaluator.evaluate(
                InteractionCommandType.NORMAL,
                IntentEvidence.LLM_CANDIDATE,
            )
            return IntentRouteResult(
                command=fallback_command,
                decision=fallback_decision,
                classifier_used=True,
                classification_error=(
                    f"{type(error).__name__}: {error}"
                ),
            )

    @staticmethod
    def _route_exact(
        command: InteractionCommand,
    ) -> IntentRouteResult:
        decision = IntentPolicyEvaluator.evaluate(
            command.command_type,
            IntentEvidence.EXACT_RULE,
        )
        return IntentRouteResult(
            command=command,
            decision=decision,
        )
