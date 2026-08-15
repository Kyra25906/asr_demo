"""呈现文案目录：把语义意图翻译成指定模式的最终文字。"""

from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from src.core.presentation_intent import PresentationIntent
from src.core.presentation_message import MessageKind


class RecordAckResult(str, Enum):
    """实验记录回执的三种真实结果。"""

    RECORDED = "recorded"
    DEGRADED = "degraded"
    FAILED = "failed"


class ConfirmationAckResult(str, Enum):
    """问题确认回执的两种真实结果。"""

    ANSWERED = "answered"
    CONFIRMED = "confirmed"


@dataclass(frozen=True)
class ReviewItem:
    """查看结果里的一条待确认项（只读快照）。"""

    display_number: int
    is_deferred: bool
    question: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.display_number, int)
            or isinstance(self.display_number, bool)
            or self.display_number <= 0
        ):
            raise ValueError("display_number 必须是正整数。")
        if not isinstance(self.is_deferred, bool):
            raise TypeError("is_deferred 必须是布尔值。")
        if not self.question.strip():
            raise ValueError("question 不能为空。")


_FIELD_LABELS = {
    "action": "操作",
    "object": "对象",
    "instrument": "仪器",
    "amount_value": "用量",
    "amount_unit": "单位",
    "concentration": "浓度",
    "temperature": "温度",
    "duration": "时间",
    "condition": "条件",
    "observation": "观察",
}


def copy_for_intent(
    intent: PresentationIntent,
    *,
    ui_mode: str,
) -> str:
    """生成最终文案；支持记录回执、追问、回答/确认回执、暂缓与查看列表。"""

    _validate_ui_mode(ui_mode)
    if intent.kind == MessageKind.RECORD_ACK:
        return _copy_record_ack(intent, ui_mode)
    if intent.kind == MessageKind.CLARIFICATION:
        return _copy_clarification(intent, ui_mode)
    if intent.kind == MessageKind.CONFIRMATION_ACK:
        return _copy_confirmation_ack(intent, ui_mode)
    if intent.kind == MessageKind.CLARIFICATION_DEFERRED:
        return _copy_deferred(intent, ui_mode)
    if intent.kind == MessageKind.CLARIFICATION_REVIEW:
        return _copy_review(intent)
    raise ValueError(f"文案目录暂不支持消息类型 {intent.kind.value}。")


def _validate_ui_mode(ui_mode: str) -> None:
    if ui_mode not in {"user", "admin"}:
        raise ValueError("ui_mode 必须是 user 或 admin。")


def _with_source(base: str, intent: PresentationIntent, ui_mode: str) -> str:
    """admin 模式追加来源口述编号；调用方保证 base 不含句尾标点。"""

    if ui_mode == "admin" and intent.source_segment_id is not None:
        return f"{base}（来源口述 {intent.source_segment_id}）。"
    return f"{base}。"


def _copy_record_ack(intent: PresentationIntent, ui_mode: str) -> str:
    try:
        result = RecordAckResult(intent.args["result"])
    except KeyError as error:
        raise ValueError("RECORD_ACK 缺少 result 参数。") from error
    except ValueError as error:
        raise ValueError("RECORD_ACK 的 result 参数不受支持。") from error

    if result == RecordAckResult.RECORDED:
        step_number = _require_positive_int(intent.args, "step_number")
        base = f"已记录实验步骤 {step_number}"
    elif result == RecordAckResult.DEGRADED:
        base = "原始记录已保存，结构化处理暂时不可用"
    else:
        base = "本段结构化处理失败，原始记录已保存"

    return _with_source(base, intent, ui_mode)


def _copy_clarification(intent: PresentationIntent, ui_mode: str) -> str:
    question = intent.args.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("CLARIFICATION 必须包含非空 question。")

    base = f"小科：{question}"
    if ui_mode == "admin" and intent.source_segment_id is not None:
        return f"{base}（来源口述 {intent.source_segment_id}）"
    return base


def _copy_confirmation_ack(intent: PresentationIntent, ui_mode: str) -> str:
    try:
        result = ConfirmationAckResult(intent.args["result"])
    except KeyError as error:
        raise ValueError("CONFIRMATION_ACK 缺少 result 参数。") from error
    except ValueError as error:
        raise ValueError("CONFIRMATION_ACK 的 result 参数不受支持。") from error

    display_number = _require_positive_int(intent.args, "display_number")

    if result == ConfirmationAckResult.CONFIRMED:
        base = f"已确认问题 {display_number}"
    else:
        base = _copy_answered(display_number, intent.args)

    return _with_source(base, intent, ui_mode)


def _copy_answered(display_number: int, args: Mapping[str, object]) -> str:
    resolved = args.get("resolved", False)
    if not isinstance(resolved, bool):
        raise ValueError("ANSWERED 的 resolved 必须是布尔值。")
    remaining_fields = args.get("remaining_fields", ())
    if not _is_field_tuple(remaining_fields):
        raise ValueError(
            "ANSWERED 的 remaining_fields 必须是字段名字符串元组。"
        )

    if resolved:
        return f"已补充问题 {display_number}，问题已解决"
    if remaining_fields:
        labels = "、".join(_translate_fields(remaining_fields))
        return f"已补充问题 {display_number}，仍需补充：{labels}"
    return f"已补充问题 {display_number}，仍需确认"


def _copy_deferred(intent: PresentationIntent, ui_mode: str) -> str:
    display_number = _require_positive_int(intent.args, "display_number")
    base = f"问题 {display_number} 已暂缓"
    return _with_source(base, intent, ui_mode)


def _copy_review(intent: PresentationIntent) -> str:
    """查看列表不区分 user/admin：列表本身就是定位信息。"""

    items = intent.args.get("items")
    if not isinstance(items, tuple) or not all(
        isinstance(item, ReviewItem) for item in items
    ):
        raise ValueError("CLARIFICATION_REVIEW 的 items 必须是 ReviewItem 元组。")

    if not items:
        return "当前没有待确认问题。"

    lines = [f"当前共有 {len(items)} 个待确认问题："]
    for item in items:
        status = "已暂缓" if item.is_deferred else "待回答"
        lines.append(f"- 问题 {item.display_number}（{status}）：{item.question}")
    return "\n".join(lines)


def _require_positive_int(args: Mapping[str, object], key: str) -> int:
    value = args.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} 必须是正整数。")
    return value


def _is_field_tuple(value: object) -> bool:
    if not isinstance(value, tuple):
        return False
    return all(isinstance(item, str) and item.strip() for item in value)


def _translate_fields(fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(_FIELD_LABELS.get(field, field) for field in fields)
