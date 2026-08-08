from dataclasses import dataclass

from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.pending_clarification import PendingClarification
from src.core.reply_coordinator import ReplyCoordinator


@dataclass(frozen=True)
class ClarificationCommandResult:
    """一次暂缓或回看命令的处理结果。"""

    command_type: InteractionCommandType
    deferred: PendingClarification | None = None
    unresolved: tuple[PendingClarification, ...] = ()


def try_handle_clarification_command(
    *,
    asr_result,
    session_id: str,
    segment_id: int,
    reply_coordinator: ReplyCoordinator,
    asr_store,
) -> ClarificationCommandResult | None:
    """
    尝试处理“暂缓当前问题”和“查看待确认问题”。

    返回 None 表示不是本函数负责的命令。命令原始 ASR 保存成功后，
    才允许修改内存中的问题状态。
    """

    command = InteractionCommandParser.parse(asr_result.text)

    if command.command_type not in {
        InteractionCommandType.DEFER_CURRENT,
        InteractionCommandType.REVIEW_PENDING,
    }:
        return None

    asr_store.append(
        result=asr_result,
        session_id=session_id,
        segment_id=segment_id,
    )

    if command.command_type == InteractionCommandType.DEFER_CURRENT:
        return ClarificationCommandResult(
            command_type=command.command_type,
            deferred=reply_coordinator.defer_current(
                segment_id=segment_id
            ),
            unresolved=(
                reply_coordinator.active_clarifications()
            ),
        )

    return ClarificationCommandResult(
        command_type=command.command_type,
        unresolved=reply_coordinator.active_clarifications(),
    )
