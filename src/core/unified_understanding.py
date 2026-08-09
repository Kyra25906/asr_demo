"""统一输入理解的数据合同与严格JSON解析器。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from src.core.intent_classifier import (
    IntentCandidate,
    IntentCandidateStatus,
    IntentClassifierError,
)
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.llm.validation import LLMOutputValidationError, parse_analysis


class UnifiedUnderstandingError(ValueError):
    """统一理解输出不满足正式数据合同。"""


class UnifiedInputKind(str, Enum):
    EXPERIMENT = "experiment"
    CONTROL = "control"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class ExperimentUnderstanding:
    analysis: LLMAnalysisResult


@dataclass(frozen=True)
class ControlUnderstanding:
    intent: IntentCandidate

    def __post_init__(self) -> None:
        if self.intent.status != IntentCandidateStatus.MATCHED:
            raise ValueError("control分支必须包含matched意图候选。")


@dataclass(frozen=True)
class UncertainUnderstanding:
    reason: str

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("uncertain分支必须包含非空弃权原因。")


@dataclass(frozen=True)
class UnifiedUnderstandingResult:
    """程序可信结果；raw_text不从模型响应中读取。"""

    raw_text: str
    experiment: ExperimentUnderstanding | None = None
    control: ControlUnderstanding | None = None
    uncertain: UncertainUnderstanding | None = None

    def __post_init__(self) -> None:
        if not self.raw_text.strip():
            raise ValueError("raw_text不能为空。")
        selected = sum(
            branch is not None
            for branch in (self.experiment, self.control, self.uncertain)
        )
        if selected != 1:
            raise ValueError("统一理解结果必须且只能包含一个分支。")

    @property
    def input_kind(self) -> UnifiedInputKind:
        if self.experiment is not None:
            return UnifiedInputKind.EXPERIMENT
        if self.control is not None:
            return UnifiedInputKind.CONTROL
        return UnifiedInputKind.UNCERTAIN


TOP_LEVEL_FIELDS = frozenset({
    "input_kind", "experiment", "control", "uncertain"
})
EXPERIMENT_FIELDS = frozenset({"analysis"})
CONTROL_FIELDS = frozenset({"intent"})
UNCERTAIN_FIELDS = frozenset({"reason"})


def _require_exact_fields(
    data: Mapping[str, Any],
    expected: frozenset[str],
    location: str,
) -> None:
    actual = set(data)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing or extra:
        raise UnifiedUnderstandingError(
            f"{location}字段不匹配；缺少={missing}，额外={extra}"
        )


def _require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnifiedUnderstandingError(f"{location}必须是对象。")
    return value


def parse_unified_understanding(
    content: str,
    *,
    expected_raw_text: str,
    session_id: str,
    segment_id: int,
) -> UnifiedUnderstandingResult:
    """严格解析模型输出；任何非法组合都整体拒绝。"""

    try:
        data = json.loads(content)
    except json.JSONDecodeError as error:
        raise UnifiedUnderstandingError("输出不是合法JSON。") from error
    data = _require_object(data, "顶层")
    _require_exact_fields(data, TOP_LEVEL_FIELDS, "顶层")

    try:
        kind = UnifiedInputKind(data["input_kind"])
    except (TypeError, ValueError) as error:
        raise UnifiedUnderstandingError("input_kind不受支持。") from error

    branch_names = {kind.value}
    for name in ("experiment", "control", "uncertain"):
        value = data[name]
        if name in branch_names and not isinstance(value, dict):
            raise UnifiedUnderstandingError(f"{name}分支必须是对象。")
        if name not in branch_names and value is not None:
            raise UnifiedUnderstandingError(f"未选中的{name}分支必须为null。")

    if kind == UnifiedInputKind.EXPERIMENT:
        branch = _require_object(data["experiment"], "experiment分支")
        _require_exact_fields(branch, EXPERIMENT_FIELDS, "experiment分支")
        analysis_data = _require_object(branch["analysis"], "analysis")
        try:
            analysis = parse_analysis(
                json.dumps(analysis_data, ensure_ascii=False),
                expected_raw_text=expected_raw_text,
                session_id=session_id,
                segment_id=segment_id,
            )
        except LLMOutputValidationError as error:
            raise UnifiedUnderstandingError(str(error)) from error
        return UnifiedUnderstandingResult(
            raw_text=expected_raw_text,
            experiment=ExperimentUnderstanding(analysis),
        )

    if kind == UnifiedInputKind.CONTROL:
        branch = _require_object(data["control"], "control分支")
        _require_exact_fields(branch, CONTROL_FIELDS, "control分支")
        intent_data = _require_object(branch["intent"], "intent")
        try:
            intent = IntentCandidate.from_mapping(intent_data)
            control = ControlUnderstanding(intent)
        except (IntentClassifierError, ValueError) as error:
            raise UnifiedUnderstandingError(str(error)) from error
        return UnifiedUnderstandingResult(
            raw_text=expected_raw_text,
            control=control,
        )

    branch = _require_object(data["uncertain"], "uncertain分支")
    _require_exact_fields(branch, UNCERTAIN_FIELDS, "uncertain分支")
    reason = branch["reason"]
    if not isinstance(reason, str):
        raise UnifiedUnderstandingError("uncertain.reason必须是字符串。")
    try:
        uncertain = UncertainUnderstanding(reason)
    except ValueError as error:
        raise UnifiedUnderstandingError(str(error)) from error
    return UnifiedUnderstandingResult(
        raw_text=expected_raw_text,
        uncertain=uncertain,
    )


def build_degraded_understanding(
    *,
    raw_text: str,
    session_id: str,
    segment_id: int,
    reason: str,
) -> UnifiedUnderstandingResult:
    """网络或格式失败时仅保存未分类NOTE，不产生控制候选。"""

    if not reason.strip():
        raise ValueError("降级原因不能为空。")
    event = ExperimentEvent(
        event_type=ExperimentEventType.NOTE,
        raw_text=raw_text,
        normalized_text=raw_text,
        entities=ExperimentEntities(),
        needs_confirmation=True,
        confirmation_reason=f"统一理解失败：{reason}",
        source_session_id=session_id,
        source_segment_id=segment_id,
    )
    analysis = LLMAnalysisResult(
        events=[event],
        should_ask_follow_up=True,
        follow_up_question="本段内容未能分类，请确认或稍后重试。",
        assistant_reply=None,
    )
    return UnifiedUnderstandingResult(
        raw_text=raw_text,
        experiment=ExperimentUnderstanding(analysis),
    )
