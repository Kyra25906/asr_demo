"""加载并严格校验ASR鲁棒性口述语料计划。

语料以JSON文件形式保存在 evaluation/narration_robustness/ 下，每段口述同时携带
"用户真实想说"（spoken_text）与"喂给系统的模拟ASR噪声转写"（observed_asr_text），
以及期望的系统行为标注。本模块只负责加载与校验，不调用ASR或LLM。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.core.interaction_command import InteractionCommandType

CHALLENGE_TYPES = frozenset({
    "normal",
    "missing_fields",
    "answer_no_number",
    "answer_wrong_number",
    "answer_two_in_one",
    "answer_number_only",
    "asr_noise_control",
    "asr_noise_entity",
    "asr_noise_entity_missing",
    "asr_truncated",
    "confirm",
    "defer_current",
    "deny_correct",
    "observation_anomaly",
    "measurement",
    "uncertain_semantics",
    "end_session",
    "control_review_exact",
    "context_dependent",
    "case_variant_tolerance",
})

INPUT_KINDS = frozenset({"experiment", "control", "uncertain"})

COMMAND_VALUES = frozenset(
    command_type.value for command_type in InteractionCommandType
)

ENTITY_FIELDS = frozenset({
    "action", "object", "instrument",
    "amount_value", "amount_unit", "concentration",
    "temperature", "duration", "condition", "observation",
})


class NarrationPlanError(ValueError):
    """口述语料计划不满足数据合同。"""


def _require_exact_keys(
    data: Mapping[str, Any],
    *,
    required: set[str],
    context: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required - data.keys()
    extra = data.keys() - required - optional
    if missing:
        raise NarrationPlanError(f"{context}缺少字段：{sorted(missing)}")
    if extra:
        raise NarrationPlanError(f"{context}包含额外字段：{sorted(extra)}")


@dataclass(frozen=True)
class NarrationSegment:
    """一段不可变的口述语料及其期望系统行为。"""

    segment_id: int
    challenge_type: str
    spoken_text: str
    observed_asr_text: str
    pending_question_numbers: tuple[int, ...]
    current_question_number: int | None
    expected_input_kind: str
    expected_command: str | None
    expected_missing_fields: tuple[str, ...]
    expected_needs_confirmation: bool
    note: str = ""

    def __post_init__(self) -> None:
        if (
            isinstance(self.segment_id, bool)
            or not isinstance(self.segment_id, int)
            or self.segment_id <= 0
        ):
            raise NarrationPlanError("segment_id必须是正整数。")
        if self.challenge_type not in CHALLENGE_TYPES:
            raise NarrationPlanError(
                f"segment {self.segment_id} 的challenge_type不受支持："
                f"{self.challenge_type!r}"
            )
        if not self.spoken_text.strip():
            raise NarrationPlanError(
                f"segment {self.segment_id} 缺少真实口述文本。"
            )
        if not self.observed_asr_text.strip():
            raise NarrationPlanError(
                f"segment {self.segment_id} 缺少模拟ASR转写。"
            )
        if any(
            isinstance(number, bool)
            or not isinstance(number, int)
            or number <= 0
            for number in self.pending_question_numbers
        ):
            raise NarrationPlanError(
                f"segment {self.segment_id} 的待确认问题编号必须为正整数。"
            )
        if len(self.pending_question_numbers) != len(
            set(self.pending_question_numbers)
        ):
            raise NarrationPlanError(
                f"segment {self.segment_id} 的待确认问题编号不能重复。"
            )
        if (
            self.current_question_number is not None
            and self.current_question_number
            not in self.pending_question_numbers
        ):
            raise NarrationPlanError(
                f"segment {self.segment_id} 的当前问题必须存在于"
                "待确认问题编号中。"
            )
        if self.expected_input_kind not in INPUT_KINDS:
            raise NarrationPlanError(
                f"segment {self.segment_id} 的期望输入类别不受支持："
                f"{self.expected_input_kind!r}"
            )
        if self.expected_input_kind == "control":
            if self.expected_command not in COMMAND_VALUES:
                raise NarrationPlanError(
                    f"segment {self.segment_id} 是control段但"
                    f"expected_command非法：{self.expected_command!r}"
                )
        elif self.expected_command is not None:
            raise NarrationPlanError(
                f"segment {self.segment_id} 非control段不能携带"
                "expected_command。"
            )
        extra_fields = set(self.expected_missing_fields) - ENTITY_FIELDS
        if extra_fields:
            raise NarrationPlanError(
                f"segment {self.segment_id} 的missing字段不受支持："
                f"{sorted(extra_fields)}"
            )
        if len(self.expected_missing_fields) != len(
            set(self.expected_missing_fields)
        ):
            raise NarrationPlanError(
                f"segment {self.segment_id} 的missing字段不能重复。"
            )
        if not isinstance(self.expected_needs_confirmation, bool):
            raise NarrationPlanError(
                f"segment {self.segment_id} 的needs_confirmation必须是布尔值。"
            )


@dataclass(frozen=True)
class NarrationRobustnessPlan:
    """版本化口述鲁棒性语料计划。"""

    schema_version: int
    scenario: str
    session_id: str
    segments: tuple[NarrationSegment, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise NarrationPlanError(
                "不支持的语料计划schema_version："
                f"{self.schema_version}"
            )
        if not self.scenario.strip():
            raise NarrationPlanError("语料计划缺少场景说明。")
        if not self.session_id.strip():
            raise NarrationPlanError("语料计划缺少session_id。")
        if not self.segments:
            raise NarrationPlanError("语料计划至少需要一段口述。")
        ids = [segment.segment_id for segment in self.segments]
        if ids != list(range(1, len(self.segments) + 1)):
            raise NarrationPlanError("segment_id必须从1开始连续编号。")

    @classmethod
    def load(cls, path: Path | str) -> NarrationRobustnessPlan:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise NarrationPlanError("语料计划不是合法JSON。") from error
        if not isinstance(data, dict):
            raise NarrationPlanError("语料计划根节点必须是对象。")
        _require_exact_keys(
            data,
            required={"schema_version", "scenario", "session_id", "segments"},
            context="语料计划",
        )
        if not isinstance(data["segments"], list):
            raise NarrationPlanError("segments必须是数组。")
        segments = tuple(
            _parse_segment(item, index=index)
            for index, item in enumerate(data["segments"], start=1)
        )
        return cls(
            schema_version=data["schema_version"],
            scenario=data["scenario"],
            session_id=data["session_id"],
            segments=segments,
        )


def _parse_segment(item: object, *, index: int) -> NarrationSegment:
    if not isinstance(item, dict):
        raise NarrationPlanError(f"第 {index} 段必须是对象。")
    _require_exact_keys(
        item,
        required={
            "segment_id",
            "challenge_type",
            "spoken_text",
            "observed_asr_text",
            "pending_question_numbers",
            "current_question_number",
            "expected_input_kind",
            "expected_command",
            "expected_missing_fields",
            "expected_needs_confirmation",
        },
        optional={"note"},
        context=f"第 {index} 段",
    )
    pending = _require_int_list(
        item["pending_question_numbers"], context=f"第 {index} 段"
    )
    missing = _require_str_list(
        item["expected_missing_fields"], context=f"第 {index} 段"
    )
    current = item["current_question_number"]
    if current is not None and (
        isinstance(current, bool) or not isinstance(current, int)
    ):
        raise NarrationPlanError(
            f"第 {index} 段current_question_number必须是正整数或null。"
        )
    expected_command = item["expected_command"]
    if expected_command is not None and not isinstance(
        expected_command, str
    ):
        raise NarrationPlanError(
            f"第 {index} 段expected_command必须是字符串或null。"
        )
    if not isinstance(item["expected_needs_confirmation"], bool):
        raise NarrationPlanError(
            f"第 {index} 段expected_needs_confirmation必须是布尔值。"
        )
    return NarrationSegment(
        segment_id=item["segment_id"],
        challenge_type=item["challenge_type"],
        spoken_text=item["spoken_text"],
        observed_asr_text=item["observed_asr_text"],
        pending_question_numbers=pending,
        current_question_number=current,
        expected_input_kind=item["expected_input_kind"],
        expected_command=expected_command,
        expected_missing_fields=missing,
        expected_needs_confirmation=item["expected_needs_confirmation"],
        note=item.get("note", ""),
    )


def _require_int_list(raw: object, *, context: str) -> tuple[int, ...]:
    if not isinstance(raw, list) or not all(
        isinstance(number, int) and not isinstance(number, bool)
        for number in raw
    ):
        raise NarrationPlanError(
            f"{context}的待确认问题编号必须是正整数数组。"
        )
    return tuple(raw)


def _require_str_list(raw: object, *, context: str) -> tuple[str, ...]:
    if not isinstance(raw, list) or not all(
        isinstance(item, str) for item in raw
    ):
        raise NarrationPlanError(f"{context}的missing字段必须是字符串数组。")
    return tuple(item.strip() for item in raw)
