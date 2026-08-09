"""控制命令固定语料的数据结构，不包含录音或ASR调用。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.core.interaction_command import InteractionCommandType


class RecordingStatus(str, Enum):
    """一次录制尝试的最终状态。"""

    ACCEPTED = "accepted"
    RETRY_REQUESTED = "retry_requested"
    SKIPPED = "skipped"
    FAILED = "failed"


class SpokenTextStatus(str, Enum):
    """音频中真实原话的人工标注状态。"""

    AWAITING_REVIEW = "awaiting_review"
    USER_CONFIRMED = "user_confirmed"
    PARTIAL_USER_CONFIRMED = "partial_user_confirmed"


@dataclass(frozen=True)
class CommandCorpusPrompt:
    """采集前已经确定的一条朗读任务。"""

    sample_id: str
    expected_intent: str
    prompt_text: str
    critical_terms: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        sample_id = self.sample_id.strip()
        prompt_text = self.prompt_text.strip()
        expected_intent = self.expected_intent.strip()

        if not sample_id:
            raise ValueError("sample_id 不能为空。")
        if not prompt_text:
            raise ValueError("prompt_text 不能为空。")

        allowed_intents = {
            command_type.value
            for command_type in InteractionCommandType
        }
        if expected_intent not in allowed_intents:
            raise ValueError(
                "expected_intent 必须是已有交互意图，"
                f"当前值为：{expected_intent!r}"
            )

        terms = tuple(
            term.strip()
            for term in self.critical_terms
            if term.strip()
        )
        if len(terms) != len(set(terms)):
            raise ValueError("critical_terms 不能包含重复词。")

        object.__setattr__(self, "sample_id", sample_id)
        object.__setattr__(self, "prompt_text", prompt_text)
        object.__setattr__(self, "expected_intent", expected_intent)
        object.__setattr__(self, "critical_terms", terms)


@dataclass(frozen=True)
class RecordingAttempt:
    """一次不可变的录音尝试及其证据状态。"""

    sample_id: str
    expected_intent: str
    prompt_text: str
    attempt_number: int
    status: RecordingStatus
    audio_path: Path | None = None
    spoken_text: str | None = None
    spoken_text_status: SpokenTextStatus = (
        SpokenTextStatus.AWAITING_REVIEW
    )
    observed_asr_text: str | None = None
    capture_note: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.attempt_number <= 0:
            raise ValueError("attempt_number 必须大于 0。")

        audio_required = self.status in {
            RecordingStatus.ACCEPTED,
            RecordingStatus.RETRY_REQUESTED,
        }
        if audio_required and self.audio_path is None:
            raise ValueError(
                f"{self.status.value} 状态必须包含 audio_path。"
            )

        if self.status == RecordingStatus.FAILED:
            if not self.error or not self.error.strip():
                raise ValueError("FAILED 状态必须包含 error。")
        elif self.error is not None:
            raise ValueError("只有 FAILED 状态可以包含 error。")

        if self.spoken_text_status in {
            SpokenTextStatus.USER_CONFIRMED,
            SpokenTextStatus.PARTIAL_USER_CONFIRMED,
        }:
            if not self.spoken_text or not self.spoken_text.strip():
                raise ValueError(
                    "已人工确认原话时必须提供 spoken_text。"
                )
        elif self.spoken_text is not None:
            raise ValueError(
                "尚未人工复核时不能提前填写 spoken_text。"
            )

        if (
            self.status == RecordingStatus.SKIPPED
            and self.spoken_text_status
            != SpokenTextStatus.AWAITING_REVIEW
        ):
            raise ValueError(
                "SKIPPED 状态不能声称已经确认口述原话。"
            )

        for field_name in (
            "spoken_text",
            "observed_asr_text",
            "capture_note",
            "error",
        ):
            value = getattr(self, field_name)
            if isinstance(value, str):
                object.__setattr__(self, field_name, value.strip())

    @classmethod
    def from_prompt(
        cls,
        prompt: CommandCorpusPrompt,
        *,
        attempt_number: int,
        status: RecordingStatus,
        audio_path: Path | None = None,
        spoken_text: str | None = None,
        spoken_text_status: SpokenTextStatus = (
            SpokenTextStatus.AWAITING_REVIEW
        ),
        observed_asr_text: str | None = None,
        capture_note: str | None = None,
        error: str | None = None,
    ) -> RecordingAttempt:
        """从稳定提示项建立一次独立录音事实。"""

        return cls(
            sample_id=prompt.sample_id,
            expected_intent=prompt.expected_intent,
            prompt_text=prompt.prompt_text,
            attempt_number=attempt_number,
            status=status,
            audio_path=audio_path,
            spoken_text=spoken_text,
            spoken_text_status=spoken_text_status,
            observed_asr_text=observed_asr_text,
            capture_note=capture_note,
            error=error,
        )

    @property
    def attempt_id(self) -> str:
        """同一句提示下本次尝试的稳定唯一键。"""

        return f"{self.sample_id}:attempt:{self.attempt_number}"

    @property
    def baseline_eligible(self) -> bool:
        """是否具备进入文本与意图基线的完整证据。"""

        return (
            self.status == RecordingStatus.ACCEPTED
            and self.audio_path is not None
            and self.spoken_text_status
            == SpokenTextStatus.USER_CONFIRMED
            and bool(self.spoken_text)
            and bool(self.observed_asr_text)
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为适合JSONL持久化的纯数据。"""

        data = asdict(self)
        data["attempt_id"] = self.attempt_id
        data["status"] = self.status.value
        data["spoken_text_status"] = self.spoken_text_status.value
        data["audio_path"] = (
            self.audio_path.as_posix()
            if self.audio_path is not None
            else None
        )
        data["baseline_eligible"] = self.baseline_eligible
        return data
