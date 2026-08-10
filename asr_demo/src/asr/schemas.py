"""ASR证据合同：区分模型输出、忠实转写和派生纠错。"""

import math
from dataclasses import dataclass
from typing import Any, Mapping


ASR_EVIDENCE_SCHEMA_VERSION = 2


@dataclass(frozen=True, init=False)
class ASRResult:
    """一次ASR识别产生的不可变证据。

    ``asr_model_raw_text`` 是ASR引擎直接返回的文本字段；
    ``asr_transcript`` 是只做确定性标签清理后的忠实可读转写。
    两者都不能被术语纠正或LLM结果覆盖。
    """

    asr_transcript: str
    asr_model_raw_text: str
    audio_path: str
    audio_duration_seconds: float
    recognition_seconds: float
    model: str
    language: str
    is_final: bool

    def __init__(
        self,
        asr_transcript: str | None = None,
        asr_model_raw_text: str | None = None,
        audio_path: str = "",
        audio_duration_seconds: float = 0.0,
        recognition_seconds: float = 0.0,
        model: str = "",
        language: str = "",
        is_final: bool = True,
        *,
        text: str | None = None,
        raw_text: str | None = None,
    ) -> None:
        """构造schema v2；``text``/``raw_text``仅供旧调用过渡。"""

        transcript = self._resolve_legacy_field(
            canonical_name="asr_transcript",
            canonical_value=asr_transcript,
            legacy_name="text",
            legacy_value=text,
        )
        model_raw_text = self._resolve_legacy_field(
            canonical_name="asr_model_raw_text",
            canonical_value=asr_model_raw_text,
            legacy_name="raw_text",
            legacy_value=raw_text,
        )

        self._validate(
            asr_transcript=transcript,
            asr_model_raw_text=model_raw_text,
            audio_path=audio_path,
            audio_duration_seconds=audio_duration_seconds,
            recognition_seconds=recognition_seconds,
            model=model,
            language=language,
            is_final=is_final,
        )

        object.__setattr__(self, "asr_transcript", transcript)
        object.__setattr__(self, "asr_model_raw_text", model_raw_text)
        object.__setattr__(self, "audio_path", audio_path)
        object.__setattr__(
            self,
            "audio_duration_seconds",
            float(audio_duration_seconds),
        )
        object.__setattr__(
            self,
            "recognition_seconds",
            float(recognition_seconds),
        )
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "language", language)
        object.__setattr__(self, "is_final", is_final)

    @property
    def text(self) -> str:
        """旧名称兼容；新代码使用``asr_transcript``。"""

        return self.asr_transcript

    @property
    def raw_text(self) -> str:
        """旧名称兼容；新代码使用``asr_model_raw_text``。"""

        return self.asr_model_raw_text

    def to_dict(self) -> dict[str, Any]:
        """只写schema v2，避免继续制造含糊的新记录。"""

        return {
            "schema_version": ASR_EVIDENCE_SCHEMA_VERSION,
            "asr_transcript": self.asr_transcript,
            "asr_model_raw_text": self.asr_model_raw_text,
            "audio_path": self.audio_path,
            "audio_duration_seconds": self.audio_duration_seconds,
            "recognition_seconds": self.recognition_seconds,
            "model": self.model,
            "language": self.language,
            "is_final": self.is_final,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ASRResult":
        """读取旧schema v1或当前schema v2，不修改源字典。"""

        version = data.get("schema_version", 1)
        common_keys = {
            "audio_path",
            "audio_duration_seconds",
            "recognition_seconds",
            "model",
            "language",
            "is_final",
        }
        if version == 1:
            allowed_keys = common_keys | {"text", "raw_text"}
        elif version == ASR_EVIDENCE_SCHEMA_VERSION:
            allowed_keys = common_keys | {
                "schema_version",
                "asr_transcript",
                "asr_model_raw_text",
            }
        else:
            raise ValueError(
                "不支持的ASR证据schema_version："
                f"{version!r}"
            )
        extra_keys = set(data) - allowed_keys
        if extra_keys:
            raise ValueError(
                "ASR证据包含未知字段："
                f"{sorted(extra_keys)}"
            )
        common = {
            "audio_path": data.get("audio_path", ""),
            "audio_duration_seconds": data.get(
                "audio_duration_seconds",
                0.0,
            ),
            "recognition_seconds": data.get(
                "recognition_seconds",
                0.0,
            ),
            "model": data.get("model", ""),
            "language": data.get("language", ""),
            "is_final": data.get("is_final", True),
        }

        if version == 1:
            if "text" not in data or "raw_text" not in data:
                raise ValueError(
                    "ASR schema v1需要text和raw_text。"
                )
            return cls(
                text=data["text"],
                raw_text=data["raw_text"],
                **common,
            )
        if version == ASR_EVIDENCE_SCHEMA_VERSION:
            if (
                "asr_transcript" not in data
                or "asr_model_raw_text" not in data
            ):
                raise ValueError(
                    "ASR schema v2需要asr_transcript和"
                    "asr_model_raw_text。"
                )
            if "text" in data or "raw_text" in data:
                raise ValueError(
                    "ASR schema v2不能混入旧字段。"
                )
            return cls(
                asr_transcript=data["asr_transcript"],
                asr_model_raw_text=data["asr_model_raw_text"],
                **common,
            )

        raise AssertionError("不可达的ASR证据版本分支。")

    @staticmethod
    def _resolve_legacy_field(
        *,
        canonical_name: str,
        canonical_value: str | None,
        legacy_name: str,
        legacy_value: str | None,
    ) -> str:
        if canonical_value is not None and legacy_value is not None:
            raise ValueError(
                f"不能同时提供{canonical_name}和{legacy_name}。"
            )
        value = (
            canonical_value
            if canonical_value is not None
            else legacy_value
        )
        if value is None:
            raise ValueError(f"{canonical_name}不能为空。")
        return value

    @staticmethod
    def _validate(
        *,
        asr_transcript: str,
        asr_model_raw_text: str,
        audio_path: str,
        audio_duration_seconds: float,
        recognition_seconds: float,
        model: str,
        language: str,
        is_final: bool,
    ) -> None:
        text_fields = {
            "asr_transcript": asr_transcript,
            "asr_model_raw_text": asr_model_raw_text,
            "audio_path": audio_path,
            "model": model,
            "language": language,
        }
        for name, value in text_fields.items():
            if not isinstance(value, str):
                raise TypeError(f"{name}必须是字符串。")
        if not isinstance(
            audio_duration_seconds,
            (int, float),
        ) or isinstance(audio_duration_seconds, bool):
            raise TypeError("audio_duration_seconds必须是数字。")
        if not math.isfinite(audio_duration_seconds):
            raise ValueError("audio_duration_seconds必须是有限值。")
        if audio_duration_seconds < 0:
            raise ValueError("audio_duration_seconds不能小于0。")
        if not isinstance(
            recognition_seconds,
            (int, float),
        ) or isinstance(recognition_seconds, bool):
            raise TypeError("recognition_seconds必须是数字。")
        if not math.isfinite(recognition_seconds):
            raise ValueError("recognition_seconds必须是有限值。")
        if recognition_seconds < 0:
            raise ValueError("recognition_seconds不能小于0。")
        if not isinstance(is_final, bool):
            raise TypeError("is_final必须是布尔值。")


@dataclass(frozen=True)
class TranscriptCorrectionCandidate:
    """从ASR忠实转写派生的纠错候选，不是ASR证据本身。"""

    source_asr_transcript: str
    candidate_transcript: str
    reason: str
    requires_confirmation: bool = True

    def __post_init__(self) -> None:
        if not self.source_asr_transcript.strip():
            raise ValueError("source_asr_transcript不能为空。")
        if not self.candidate_transcript.strip():
            raise ValueError("candidate_transcript不能为空。")
        if not self.reason.strip():
            raise ValueError("reason不能为空。")
        if self.source_asr_transcript == self.candidate_transcript:
            raise ValueError("纠错候选必须与源转写不同。")
        if not isinstance(self.requires_confirmation, bool):
            raise TypeError("requires_confirmation必须是布尔值。")
