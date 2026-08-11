"""把已验证的ClarificationAction安全转换为ReplyCoordinator状态变更。"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.clarification_acceptance import (
    ClarificationAction,
    ClarificationActionType,
    ClarificationMutationPermission,
)
from src.core.reply_coordinator import ReplyCoordinator


_STATE_CHANGING_ACTIONS = frozenset({
    ClarificationActionType.CREATE,
    ClarificationActionType.DEFER,
    ClarificationActionType.ANSWER,
    ClarificationActionType.CONFIRM,
    ClarificationActionType.REJECT_SUGGESTION,
})


@dataclass(frozen=True)
class ClarificationExecutionResult:
    """一次动作执行的结果，无论成功、被拒绝还是跳过。"""

    request_id: str
    session_id: str
    segment_id: int
    action_type: ClarificationActionType
    state_changed: bool
    reason: str
    affected_clarification_id: str | None = None
    affected_display_number: int | None = None
    answer_text_received: bool = False


class ClarificationExecutor:
    """只把已验证的ClarificationAction翻译成ReplyCoordinator调用。"""

    def __init__(self, reply_coordinator: ReplyCoordinator) -> None:
        self._coordinator = reply_coordinator

    def execute(
        self,
        action: ClarificationAction,
    ) -> ClarificationExecutionResult:
        self._validate_action(action)

        if action.action_type == ClarificationActionType.NO_ACTION:
            return self._result(action, state_changed=False,
                                reason="NO_ACTION 无需状态变更。")

        if action.action_type == ClarificationActionType.REVIEW:
            return self._result(action, state_changed=False,
                                reason="REVIEW 是只读动作，不产生状态变更。")

        if action.action_type == ClarificationActionType.CREATE:
            return self._execute_create(action)

        if action.action_type == ClarificationActionType.DEFER:
            return self._execute_targeted(action, "defer")

        if action.action_type == ClarificationActionType.ANSWER:
            return self._execute_answer(action)

        if action.action_type in {
            ClarificationActionType.CONFIRM,
            ClarificationActionType.REJECT_SUGGESTION,
        }:
            return self._execute_targeted(action, "confirm")

        raise ValueError(f"未知动作类型：{action.action_type}")

    def _execute_create(
        self,
        action: ClarificationAction,
    ) -> ClarificationExecutionResult:
        new = self._coordinator.register_clarification(
            segment_id=action.segment_id,
            raw_text=action.asr_transcript,
            question=action.question,
            missing_fields=action.missing_fields,
            requires_confirmation=action.requires_confirmation,
        )
        return self._result(
            action,
            state_changed=True,
            reason=f"已创建待确认问题 {new.display_number}。",
            affected_clarification_id=new.clarification_id,
            affected_display_number=new.display_number,
        )

    def _execute_targeted(
        self,
        action: ClarificationAction,
        operation: str,
    ) -> ClarificationExecutionResult:
        try:
            if operation == "defer":
                updated = self._coordinator.defer_clarification(
                    clarification_id=action.target_clarification_id,
                    expected_revision=action.expected_revision,
                    segment_id=action.segment_id,
                )
            else:
                updated = self._coordinator.confirm_clarification(
                    clarification_id=action.target_clarification_id,
                    expected_revision=action.expected_revision,
                    segment_id=action.segment_id,
                )
        except ValueError as error:
            return self._result(
                action,
                state_changed=False,
                reason=str(error),
            )

        return self._result(
            action,
            state_changed=True,
            reason=(
                f"{action.action_type.value} 操作完成，"
                f"问题 {updated.display_number} 状态已更新。"
            ),
            affected_clarification_id=updated.clarification_id,
            affected_display_number=updated.display_number,
        )

    def _execute_answer(
        self,
        action: ClarificationAction,
    ) -> ClarificationExecutionResult:
        try:
            target = self._coordinator._find_clarification(
                action.target_clarification_id,
            )
            if target is None:
                return self._result(
                    action,
                    state_changed=False,
                    reason=f"未找到目标问题：{action.target_clarification_id}",
                )
            if target.revision != action.expected_revision:
                return self._result(
                    action,
                    state_changed=False,
                    reason=(
                        f"待确认项版本已变更（期望 {action.expected_revision}，"
                        f"当前 {target.revision}），拒绝过期答复。"
                    ),
                )
            if not target.is_active:
                return self._result(
                    action,
                    state_changed=False,
                    reason="只能答复 ACTIVE 状态的待确认项。",
                )
        except ValueError as error:
            return self._result(
                action,
                state_changed=False,
                reason=str(error),
            )

        return self._result(
            action,
            state_changed=False,
            answer_text_received=True,
            reason=(
                f"收到对问题 {target.display_number} 的答复"
                f"\"{action.answer_text}\"，"
                "但动作未携带解析后的实体字段，未修改待确认状态。"
            ),
        )

    def _validate_action(self, action: ClarificationAction) -> None:
        if (
            action.action_type in _STATE_CHANGING_ACTIONS
            and not action.requires_evidence_persistence
        ):
            raise ValueError(
                f"{action.action_type.value} 动作要求"
                " requires_evidence_persistence=True，"
                "ClarificationAction 验证层应已拦截此问题。"
            )

    @staticmethod
    def _result(
        action: ClarificationAction,
        *,
        state_changed: bool,
        reason: str,
        affected_clarification_id: str | None = None,
        affected_display_number: int | None = None,
        answer_text_received: bool = False,
    ) -> ClarificationExecutionResult:
        return ClarificationExecutionResult(
            request_id=action.request_id,
            session_id=action.session_id,
            segment_id=action.segment_id,
            action_type=action.action_type,
            state_changed=state_changed,
            reason=reason,
            affected_clarification_id=affected_clarification_id,
            affected_display_number=affected_display_number,
            answer_text_received=answer_text_received,
        )
