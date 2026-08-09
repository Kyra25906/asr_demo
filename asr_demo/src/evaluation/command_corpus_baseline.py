"""从独立采集证据生成固定命令ASR基线。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from scripts.evaluate_asr_commands import evaluate_manifest
from src.core.interaction_command import InteractionCommandParser
from src.evaluation.command_corpus_plan import CommandCorpusPlan


class Recognizer(Protocol):
    def recognize(self, audio_path: Path, *, language: str = "auto"): ...


class CaptureBaselineError(ValueError):
    """采集证据不足以生成可信基线。"""


def load_accepted_attempts(path: Path) -> dict[str, dict[str, Any]]:
    """只选择人工接受记录，并要求每个sample_id唯一。"""

    accepted: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise CaptureBaselineError(
                f"第{line_number}行不是合法JSON。"
            ) from error
        if row.get("status") != "accepted":
            continue
        sample_id = row.get("sample_id")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise CaptureBaselineError("accepted记录缺少sample_id。")
        if sample_id in accepted:
            raise CaptureBaselineError(
                f"sample_id存在多条accepted记录：{sample_id}"
            )
        if row.get("spoken_text_status") != "user_confirmed":
            raise CaptureBaselineError(
                f"{sample_id}的原话尚未人工确认。"
            )
        spoken_text = row.get("spoken_text")
        if not isinstance(spoken_text, str) or not spoken_text.strip():
            raise CaptureBaselineError(f"{sample_id}缺少人工确认原话。")
        audio_path = row.get("audio_path")
        if not isinstance(audio_path, str) or not Path(audio_path).is_file():
            raise CaptureBaselineError(f"{sample_id}的WAV不存在。")
        accepted[sample_id] = row
    return accepted


def build_capture_baseline(
    plan: CommandCorpusPlan,
    accepted: dict[str, dict[str, Any]],
    *,
    recognizer: Recognizer,
    language: str = "auto",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """按计划顺序识别accepted WAV并计算静态指标。"""

    plan_ids = {prompt.sample_id for prompt in plan.prompts}
    missing = plan_ids - accepted.keys()
    extra = accepted.keys() - plan_ids
    if missing or extra:
        raise CaptureBaselineError(
            f"采集证据与计划不一致；缺少={sorted(missing)}，"
            f"额外={sorted(extra)}"
        )

    rows: list[dict[str, Any]] = []
    for index, prompt in enumerate(plan.prompts, start=1):
        attempt = accepted[prompt.sample_id]
        result = recognizer.recognize(
            Path(attempt["audio_path"]), language=language
        )
        rows.append({
            "sample_id": prompt.sample_id,
            "audio_path": str(Path(attempt["audio_path"]).resolve()),
            "reference_text": attempt["spoken_text"],
            "reference_status": "user_confirmed",
            "observed_asr_text": result.text,
            "observed_asr_raw_text": result.raw_text,
            "recognition_seconds": result.recognition_seconds,
            "expected_intent": prompt.expected_intent,
            "session_id": "command_corpus_capture_20260809",
            "segment_id": index,
            "critical_terms": list(prompt.critical_terms),
            "source_attempt_id": attempt.get("attempt_id"),
            "language": language,
        })
    metrics = evaluate_manifest(rows)
    reference_intent_matches = 0
    asr_induced_misses = 0
    for row, detail in zip(rows, metrics["details"], strict=True):
        reference_prediction = InteractionCommandParser.parse(
            row["reference_text"]
        ).command_type.value
        reference_matched = reference_prediction == row["expected_intent"]
        reference_intent_matches += int(reference_matched)
        if not detail["intent_match"] and reference_matched:
            asr_induced_misses += 1
        detail["reference_predicted_intent"] = reference_prediction
        detail["reference_intent_match"] = reference_matched

    metrics["reference_intent_match_count"] = reference_intent_matches
    metrics["rule_coverage_miss_count"] = (
        len(rows) - reference_intent_matches
    )
    metrics["asr_induced_intent_miss_count"] = asr_induced_misses
    return rows, metrics
