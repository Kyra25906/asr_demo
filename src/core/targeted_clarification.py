from dataclasses import dataclass
from enum import Enum

from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.reply_coordinator import ReplyCoordinator


class TargetedAnswerStatus(str, Enum):
    """指定编号回答在进入后台处理前的检查结果。"""

    READY = "ready"
    NOT_FOUND = "not_found"
    MISSING_ANSWER = "missing_answer"


@dataclass(frozen=True)
class TargetedAnswerRequest:
    """一条经过确定性编号检查的指定问题回答。"""

    command_type: InteractionCommandType
    status: TargetedAnswerStatus
    raw_text: str
    display_number: int
    answer_text: str | None = None
    clarification_id: str | None = None
    confirms_suggestion: bool = False


def resolve_targeted_answer(
    text: str,
    *,
    reply_coordinator: ReplyCoordinator,
) -> TargetedAnswerRequest | None:
    """
    解析“问题2，……”并检查编号是否对应未解决问题。

    返回 None 表示普通实验口述。这里不调用 LLM、不写文件、
    不改变问题状态，只生成供主流程使用的路由请求。
    """

    command = InteractionCommandParser.parse(text)
    if command.command_type != InteractionCommandType.TARGETED_ANSWER:
        return None

    display_number = command.target_question_number
    if display_number is None:
        raise RuntimeError("指定问题命令缺少问题编号。")

    clarification = (
        reply_coordinator
        .find_unresolved_by_display_number(display_number)
    )
    if clarification is None:
        return TargetedAnswerRequest(
            command_type=command.command_type,
            status=TargetedAnswerStatus.NOT_FOUND,
            raw_text=command.raw_text,
            display_number=display_number,
            answer_text=command.answer_text,
        )

    if not command.answer_text:
        return TargetedAnswerRequest(
            command_type=command.command_type,
            status=TargetedAnswerStatus.MISSING_ANSWER,
            raw_text=command.raw_text,
            display_number=display_number,
            clarification_id=clarification.clarification_id,
        )

    return TargetedAnswerRequest(
        command_type=command.command_type,
        status=TargetedAnswerStatus.READY,
        raw_text=command.raw_text,
        display_number=display_number,
        answer_text=command.answer_text,
        clarification_id=clarification.clarification_id,
        confirms_suggestion=_is_explicit_confirmation(
            command.answer_text
        ),
    )


def _is_explicit_confirmation(answer_text: str) -> bool:
    """识别指定答复中不会与普通补充字段混淆的肯定开头。"""

    exact_answers = {
        "是",
        "是的",
        "对",
        "对的",
        "确认",
        "没错",
        "正确",
    }
    safe_prefixes = (
        "是的是",
        "没错是",
        "确认是",
    )

    return (
        answer_text in exact_answers
        or answer_text.startswith(safe_prefixes)
    )
