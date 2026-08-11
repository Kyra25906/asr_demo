"""对固定控制命令语料计算当前静态基线。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)


ALLOWED_REFERENCE_STATUSES = {
    "user_confirmed",
    "needs_user_label",
}
ALLOWED_INTENTS = {item.value for item in InteractionCommandType}
REQUIRED_FIELDS = {
    "sample_id",
    "audio_path",
    "reference_text",
    "reference_status",
    "observed_asr_text",
    "expected_intent",
    "session_id",
    "segment_id",
    "critical_terms",
}


class EvaluationDataError(ValueError):
    """评测数据不完整或不可信。"""


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """读取并严格校验 JSONL 清单。"""

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise EvaluationDataError(
                f"第 {line_number} 行不是合法 JSON：{error.msg}"
            ) from error

        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            raise EvaluationDataError(
                f"第 {line_number} 行缺少字段：{sorted(missing)}"
            )

        sample_id = row["sample_id"]
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise EvaluationDataError("sample_id 必须是非空字符串")
        if sample_id in seen_ids:
            raise EvaluationDataError(f"sample_id 重复：{sample_id}")
        seen_ids.add(sample_id)

        if row["reference_status"] not in ALLOWED_REFERENCE_STATUSES:
            raise EvaluationDataError(
                f"{sample_id} 的 reference_status 不合法"
            )
        if row["expected_intent"] not in ALLOWED_INTENTS:
            raise EvaluationDataError(
                f"{sample_id} 的 expected_intent 不合法"
            )
        if (
            row["reference_status"] == "user_confirmed"
            and not row["reference_text"]
        ):
            raise EvaluationDataError(
                f"{sample_id} 已确认却没有 reference_text"
            )

        audio_path = Path(row["audio_path"])
        if not audio_path.is_absolute():
            audio_path = (path.parent / audio_path).resolve()
        if not audio_path.is_file():
            raise EvaluationDataError(
                f"{sample_id} 的音频文件不存在：{audio_path}"
            )

        normalized_row = dict(row)
        normalized_row["audio_path"] = str(audio_path)
        rows.append(normalized_row)

    if not rows:
        raise EvaluationDataError("评测清单不能为空")
    return rows


def _same_text(left: str, right: str) -> bool:
    return (
        InteractionCommandParser.normalize(left)
        == InteractionCommandParser.normalize(right)
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def evaluate_manifest(
    rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """用已经保存的 ASR 文本评估当前确定性解析器。"""

    samples = list(rows)
    labeled = [
        row
        for row in samples
        if row["reference_status"] == "user_confirmed"
    ]
    exact_matches = sum(
        _same_text(row["reference_text"], row["observed_asr_text"])
        for row in labeled
    )

    details: list[dict[str, Any]] = []
    intent_matches = 0
    command_misses = 0
    false_triggers = 0

    for row in samples:
        predicted = InteractionCommandParser.parse(
            row["observed_asr_text"]
        ).command_type.value
        expected = row["expected_intent"]
        matched = predicted == expected
        intent_matches += int(matched)
        if expected != "normal" and predicted == "normal":
            command_misses += 1
        if expected == "normal" and predicted != "normal":
            false_triggers += 1
        details.append({
            "sample_id": row["sample_id"],
            "expected_intent": expected,
            "predicted_intent": predicted,
            "intent_match": matched,
            "text_match": (
                _same_text(
                    row["reference_text"],
                    row["observed_asr_text"],
                )
                if row["reference_status"] == "user_confirmed"
                else None
            ),
        })

    return {
        "sample_count": len(samples),
        "labeled_text_sample_count": len(labeled),
        "exact_text_match_count": exact_matches,
        "exact_text_accuracy": _ratio(exact_matches, len(labeled)),
        "intent_sample_count": len(samples),
        "intent_match_count": intent_matches,
        "intent_accuracy": _ratio(intent_matches, len(samples)),
        "control_command_miss_count": command_misses,
        "normal_content_false_trigger_count": false_triggers,
        "details": details,
    }


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    default_manifest = (
        project_root / "evaluation" / "asr_commands" / "manifest.jsonl"
    )
    default_output = (
        project_root / "evaluation" / "asr_commands" / "baseline.json"
    )

    parser = argparse.ArgumentParser(
        description="计算控制命令 ASR 与意图解析静态基线。"
    )
    parser.add_argument("--manifest", type=Path, default=default_manifest)
    parser.add_argument("--output", type=Path, default=default_output)
    args = parser.parse_args()

    report = evaluate_manifest(load_manifest(args.manifest))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"样本数：{report['sample_count']}")
    print(
        "可标注文本精确率："
        f"{report['exact_text_match_count']}/"
        f"{report['labeled_text_sample_count']}"
    )
    print(
        "当前命令解析意图准确率："
        f"{report['intent_match_count']}/"
        f"{report['intent_sample_count']}"
    )
    print(f"控制命令漏触发：{report['control_command_miss_count']}")
    print(
        "普通内容误触发："
        f"{report['normal_content_false_trigger_count']}"
    )
    print(f"报告已保存：{args.output}")


if __name__ == "__main__":
    main()
