from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from src.core.reply_coordinator import PreparedConfirmation


class ConfirmationDecision(str, Enum):
    """用户对待确认项作出的回答类别。"""

    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    CORRECTED = "corrected"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class ConfirmationRecord:
    """一条可以追溯原问题和原始语音的确认答复记录。"""

    record_id: str
    session_id: str
    clarification_id: str
    source_segment_id: int
    answer_segment_id: int
    answer_raw_text: str
    decision: ConfirmationDecision
    fully_resolved: bool
    answer_audio_path: str | None = None
    confirmed_fields: tuple[str, ...] = ()
    corrected_fields: dict[str, str] = field(default_factory=dict)
    remaining_fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        self._require_text(self.record_id, "record_id")
        self._require_text(self.session_id, "session_id")
        self._require_text(
            self.clarification_id,
            "clarification_id",
        )
        self._require_text(
            self.answer_raw_text,
            "answer_raw_text",
        )

        if not isinstance(
            self.decision,
            ConfirmationDecision,
        ):
            raise ValueError(
                "decision 必须是 ConfirmationDecision。"
            )
        if not isinstance(self.fully_resolved, bool):
            raise ValueError(
                "fully_resolved 必须是布尔值。"
            )
        if not isinstance(self.confirmed_fields, tuple):
            raise ValueError(
                "confirmed_fields 必须是 tuple。"
            )
        if not isinstance(self.remaining_fields, tuple):
            raise ValueError(
                "remaining_fields 必须是 tuple。"
            )
        if not isinstance(self.corrected_fields, dict):
            raise ValueError(
                "corrected_fields 必须是 dict。"
            )

        if self.source_segment_id <= 0:
            raise ValueError(
                "source_segment_id 必须大于 0。"
            )
        if self.answer_segment_id <= self.source_segment_id:
            raise ValueError(
                "answer_segment_id 必须大于 "
                "source_segment_id。"
            )
        if (
            self.answer_audio_path is not None
            and not self.answer_audio_path.strip()
        ):
            raise ValueError(
                "answer_audio_path 不能是空字符串。"
            )

        self._validate_field_names(
            self.confirmed_fields,
            "confirmed_fields",
        )
        self._validate_field_names(
            self.remaining_fields,
            "remaining_fields",
        )

        if self.fully_resolved and self.remaining_fields:
            raise ValueError(
                "fully_resolved 为 true 时，"
                "remaining_fields 必须为空。"
            )

        for field_name, value in self.corrected_fields.items():
            self._require_text(
                field_name,
                "corrected_fields 的字段名",
            )
            self._require_text(
                value,
                "corrected_fields 的字段值",
            )

        if (
            self.decision == ConfirmationDecision.CORRECTED
            and not self.corrected_fields
        ):
            raise ValueError(
                "corrected 决策必须包含 corrected_fields。"
            )

    def to_dict(self) -> dict[str, Any]:
        """转换为适合 JSON 序列化的普通字典。"""

        data = asdict(self)
        data["decision"] = self.decision.value
        return data

    @classmethod
    def from_prepared_confirmation(
        cls,
        *,
        session_id: str,
        answer_audio_path: str,
        prepared: "PreparedConfirmation",
    ) -> "ConfirmationRecord":
        """由已经准备好的肯定确认计划创建持久化记录。"""

        return cls(
            record_id=(
                f"{session_id}:confirmation:"
                f"{prepared.answer_segment_id}:"
                f"{prepared.clarification_id}"
            ),
            session_id=session_id,
            clarification_id=prepared.clarification_id,
            source_segment_id=prepared.source_segment_id,
            answer_segment_id=prepared.answer_segment_id,
            answer_raw_text=prepared.answer_raw_text,
            answer_audio_path=answer_audio_path,
            decision=ConfirmationDecision.CONFIRMED,
            fully_resolved=prepared.fully_resolved,
            remaining_fields=prepared.remaining_fields,
        )

    @classmethod
    def from_executed_confirmation(
        cls,
        *,
        session_id: str,
        clarification_id: str,
        source_segment_id: int,
        answer_segment_id: int,
        answer_raw_text: str,
        answer_audio_path: str,
        fully_resolved: bool,
        remaining_fields: tuple[str, ...],
    ) -> "ConfirmationRecord":
        """由统一链执行成功后的确认结果创建持久化记录。

        统一链的 confirm 动作不经过旧的 prepare/commit 流程，
        因此记录直接由执行结果显式字段构造。
        """

        return cls(
            record_id=(
                f"{session_id}:confirmation:"
                f"{answer_segment_id}:"
                f"{clarification_id}"
            ),
            session_id=session_id,
            clarification_id=clarification_id,
            source_segment_id=source_segment_id,
            answer_segment_id=answer_segment_id,
            answer_raw_text=answer_raw_text,
            answer_audio_path=answer_audio_path,
            decision=ConfirmationDecision.CONFIRMED,
            fully_resolved=fully_resolved,
            remaining_fields=remaining_fields,
        )

    @staticmethod
    def _require_text(
        value: str,
        field_name: str,
    ) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{field_name} 不能为空。"
            )

    @staticmethod
    def _validate_field_names(
        values: tuple[str, ...],
        field_name: str,
    ) -> None:
        if len(values) != len(set(values)):
            raise ValueError(
                f"{field_name} 不得重复。"
            )
        if any(
            not isinstance(value, str)
            or not value.strip()
            for value in values
        ):
            raise ValueError(
                f"{field_name} 不能包含空字段名。"
            )
