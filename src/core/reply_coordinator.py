import re
from dataclasses import dataclass, fields

from src.core.pending_clarification import PendingClarification
from src.llm.schemas import ExperimentEntities, LLMAnalysisResult


FIELD_LABELS = {
    "amount_value": "体积或质量数值",
    "amount_unit": "体积或质量单位",
    "concentration": "浓度",
    "temperature": "温度",
    "duration": "时间",
    "condition": "实验条件",
}


@dataclass(frozen=True)
class CoordinatedReply:
    """协调器交给终端或未来 TTS 层的一条回复。"""

    clarification_id: str
    source_segment_id: int
    source_raw_text: str
    text: str


@dataclass(frozen=True)
class ConfirmationResolution:
    """一次明确肯定答复成功匹配到待确认项后的结果。"""

    clarification_id: str
    source_segment_id: int
    answer_segment_id: int
    answer_raw_text: str
    fully_resolved: bool
    remaining_fields: tuple[str, ...]


@dataclass(frozen=True)
class PreparedConfirmation:
    """尚未提交的确认计划；创建它不会修改协调器状态。"""

    clarification_id: str
    source_segment_id: int
    answer_segment_id: int
    answer_raw_text: str
    fully_resolved: bool
    remaining_fields: tuple[str, ...]
    expected_revision: int


class ReplyCoordinator:
    """
    管理一次实验会话中的待确认项。

    ingest_analysis 只接收结构化数据，不访问麦克风、文件或模型。
    pop_next_reply 每次最多返回一条回复，由主流程决定何时展示或播放。
    """

    def __init__(self) -> None:
        self._clarifications: list[PendingClarification] = []
        self._next_display_number = 1
        self._current_clarification_id: str | None = None

    def ingest_analysis(
        self,
        *,
        segment_id: int,
        raw_text: str,
        analysis: LLMAnalysisResult,
    ) -> None:
        """先用当前结果更新旧问题，再登记当前段的新问题。"""

        if segment_id <= 0:
            raise ValueError("segment_id 必须大于 0。")
        if not raw_text.strip():
            raise ValueError("raw_text 不能为空。")

        supplied_fields = self._collect_supplied_fields(analysis)
        self._apply_supplied_fields(
            supplied_fields,
            segment_id=segment_id,
        )

        if analysis.should_ask_follow_up:
            self._register_clarification(
                segment_id=segment_id,
                raw_text=raw_text,
                analysis=analysis,
            )

    def pop_next_reply(self) -> CoordinatedReply | None:
        """按来源段号选择一条尚未播报的最早问题。"""

        candidates = [
            clarification
            for clarification in self._clarifications
            if clarification.is_active and clarification.reply_pending
        ]

        if not candidates:
            return None

        selected = min(
            candidates,
            key=lambda item: item.source_segment_id,
        )

        index = self._clarifications.index(selected)
        self._clarifications[index] = selected.mark_replied()
        self._current_clarification_id = selected.clarification_id

        return CoordinatedReply(
            clarification_id=selected.clarification_id,
            source_segment_id=selected.source_segment_id,
            source_raw_text=selected.source_raw_text,
            text=self._build_reply_text(selected),
        )

    def active_clarifications(self) -> tuple[PendingClarification, ...]:
        """返回全部未解决项，兼容现有会话收尾调用。"""

        return tuple(
            clarification
            for clarification in self._clarifications
            if clarification.is_unresolved
        )

    def current_clarification(self) -> PendingClarification | None:
        """返回最近一次交给用户的、仍处于 ACTIVE 的问题。"""

        for clarification in self._clarifications:
            if (
                clarification.clarification_id
                == self._current_clarification_id
                and clarification.is_active
            ):
                return clarification

        return None

    def defer_current(
        self,
        *,
        segment_id: int,
    ) -> PendingClarification | None:
        """暂缓当前问题；没有当前问题时不猜测目标。"""

        current = self.current_clarification()
        if current is None:
            return None

        updated = current.defer(segment_id=segment_id)
        index = self._clarifications.index(current)
        self._clarifications[index] = updated
        self._current_clarification_id = None
        return updated

    def reactivate_question(
        self,
        *,
        display_number: int,
        segment_id: int,
    ) -> PendingClarification | None:
        """按稳定显示编号重新激活一条暂缓问题。"""

        for index, clarification in enumerate(self._clarifications):
            if clarification.display_number != display_number:
                continue

            updated = clarification.reactivate(
                segment_id=segment_id
            )
            self._clarifications[index] = updated
            return updated if updated != clarification else None

        return None

    def try_confirm_oldest(
        self,
        *,
        segment_id: int,
        raw_text: str,
    ) -> ConfirmationResolution | None:
        """
        用明确肯定答复确认最早的 ASR 错词待确认项。

        返回 None 表示：
        - 当前没有 ASR 确认项；或
        - 文本不是受支持的明确肯定答复。
        """

        prepared = self.prepare_confirmation(
            segment_id=segment_id,
            raw_text=raw_text,
        )

        if prepared is None:
            return None

        return self.commit_confirmation(
            prepared
        )

    def prepare_confirmation(
        self,
        *,
        segment_id: int,
        raw_text: str,
    ) -> PreparedConfirmation | None:
        """计算确认结果，但不修改任何待确认状态。"""

        if segment_id <= 0:
            raise ValueError("segment_id 必须大于 0。")
        if not raw_text.strip():
            raise ValueError("raw_text 不能为空。")
        if not self._is_affirmative_answer(raw_text):
            return None

        candidates = [
            clarification
            for clarification in self._clarifications
            if (
                clarification.is_active
                and clarification.requires_confirmation
                and clarification.source_segment_id < segment_id
            )
        ]

        if not candidates:
            return None

        selected = min(
            candidates,
            key=lambda item: item.source_segment_id,
        )
        preview = selected.confirm(
            segment_id=segment_id
        )

        return PreparedConfirmation(
            clarification_id=selected.clarification_id,
            source_segment_id=selected.source_segment_id,
            answer_segment_id=segment_id,
            answer_raw_text=raw_text,
            fully_resolved=not preview.is_active,
            remaining_fields=preview.missing_fields,
            expected_revision=selected.revision,
        )

    def commit_confirmation(
        self,
        prepared: PreparedConfirmation,
    ) -> ConfirmationResolution:
        """在外部保存成功后，提交已经准备好的状态变化。"""

        matches = [
            clarification
            for clarification in self._clarifications
            if clarification.clarification_id == prepared.clarification_id
        ]

        if not matches:
            raise ValueError(
                "待提交的确认项已经不存在。"
            )

        selected = matches[0]

        if (
            not selected.is_active
            or not selected.requires_confirmation
            or selected.revision != prepared.expected_revision
        ):
            raise ValueError(
                "待确认项状态已经变化，不能提交旧确认计划。"
            )

        updated = selected.confirm(
            segment_id=prepared.answer_segment_id
        )
        index = self._clarifications.index(selected)
        self._clarifications[index] = updated

        return ConfirmationResolution(
            clarification_id=updated.clarification_id,
            source_segment_id=updated.source_segment_id,
            answer_segment_id=prepared.answer_segment_id,
            answer_raw_text=prepared.answer_raw_text,
            fully_resolved=not updated.is_active,
            remaining_fields=updated.missing_fields,
        )

    def _apply_supplied_fields(
        self,
        supplied_fields: set[str],
        *,
        segment_id: int,
    ) -> None:
        updated_items = []

        for clarification in self._clarifications:
            if clarification.source_segment_id < segment_id:
                clarification = clarification.supply_fields(
                    supplied_fields,
                    segment_id=segment_id,
                )

            updated_items.append(clarification)

        self._clarifications = updated_items

    def _register_clarification(
        self,
        *,
        segment_id: int,
        raw_text: str,
        analysis: LLMAnalysisResult,
    ) -> None:
        question = analysis.follow_up_question

        if not question or not question.strip():
            raise ValueError(
                "需要追问时 follow_up_question 不能为空。"
            )

        missing_fields = tuple(
            dict.fromkeys(
                field_name
                for event in analysis.events
                for field_name in event.missing_fields
            )
        )
        requires_confirmation = any(
            event.needs_confirmation
            for event in analysis.events
        )

        clarification = PendingClarification(
            clarification_id=f"segment-{segment_id}",
            display_number=self._next_display_number,
            source_segment_id=segment_id,
            source_raw_text=raw_text,
            question=question,
            missing_fields=missing_fields,
            requires_confirmation=requires_confirmation,
        )

        self._clarifications.append(clarification)
        self._next_display_number += 1

    @staticmethod
    def _collect_supplied_fields(
        analysis: LLMAnalysisResult,
    ) -> set[str]:
        supplied_fields: set[str] = set()

        for event in analysis.events:
            for entity_field in fields(ExperimentEntities):
                value = getattr(event.entities, entity_field.name)

                if isinstance(value, str) and value.strip():
                    supplied_fields.add(entity_field.name)

        return supplied_fields

    @staticmethod
    def _build_reply_text(
        clarification: PendingClarification,
    ) -> str:
        source = (
            f"关于第 {clarification.source_segment_id} 段"
            f"“{clarification.source_raw_text}”"
        )

        if clarification.revision == 1:
            question = clarification.question
        elif clarification.missing_fields:
            labels = [
                FIELD_LABELS.get(field_name, field_name)
                for field_name in clarification.missing_fields
            ]
            question = "仍需确认：" + "、".join(labels) + "。"
        else:
            question = clarification.question

        return f"{source}：{question}"

    @staticmethod
    def _is_affirmative_answer(
        raw_text: str,
    ) -> bool:
        """保守识别不会与普通实验操作混淆的肯定答复。"""

        normalized = re.sub(
            r"[\s，。！？、,.!?；;：:]",
            "",
            raw_text,
        )

        exact_answers = {
            "是",
            "是的",
            "对",
            "对的",
            "正确",
            "没错",
            "确认",
        }

        if normalized in exact_answers:
            return True

        safe_prefixes = (
            "是的是",
            "没错是",
            "确认是",
        )

        return normalized.startswith(
            safe_prefixes
        )
