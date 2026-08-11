"""在同一批固定 WAV 上比较 SenseVoice 语言参数。"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Protocol, Sequence

from scripts.evaluate_asr_commands import evaluate_manifest, load_manifest
from src.asr.languages import SUPPORTED_SENSEVOICE_LANGUAGES


class Recognizer(Protocol):
    """评测脚本依赖的最小识别接口，便于用假对象做单元测试。"""

    def recognize(self, audio_path: Path, *, language: str): ...


def validate_languages(languages: Sequence[str]) -> tuple[str, ...]:
    """拒绝空列表、重复值和当前 SenseVoice 不支持的值。"""

    normalized = tuple(item.strip() for item in languages)
    if not normalized or any(not item for item in normalized):
        raise ValueError("至少需要一个非空 language 参数")
    if len(set(normalized)) != len(normalized):
        raise ValueError("language 参数不能重复")

    unsupported = set(normalized) - SUPPORTED_SENSEVOICE_LANGUAGES
    if unsupported:
        raise ValueError(
            f"不支持的 language：{sorted(unsupported)}"
        )
    return normalized


def compare_languages(
    rows: Sequence[dict[str, Any]],
    *,
    recognizer: Recognizer,
    languages: Sequence[str] = ("auto", "zh"),
) -> dict[str, Any]:
    """识别同一批音频并分别计算文本及命令意图指标。"""

    checked_languages = validate_languages(languages)
    candidates: dict[str, Any] = {}

    for language in checked_languages:
        candidate_rows: list[dict[str, Any]] = []
        recognitions: list[dict[str, Any]] = []

        for source_row in rows:
            result = recognizer.recognize(
                Path(source_row["audio_path"]),
                language=language,
            )
            candidate_row = deepcopy(source_row)
            candidate_row["observed_asr_text"] = (
                result.asr_transcript
            )
            candidate_rows.append(candidate_row)
            recognitions.append({
                "sample_id": source_row["sample_id"],
                "text": result.asr_transcript,
                "raw_text": result.asr_model_raw_text,
                "recognition_seconds": result.recognition_seconds,
            })

        candidates[language] = {
            "metrics": evaluate_manifest(candidate_rows),
            "recognitions": recognitions,
        }

    return {
        "schema_version": 1,
        "experiment": "sensevoice_language_comparison",
        "controlled_variables": {
            "use_itn": True,
            "batch_size_s": 60,
            "audio_order_preserved": True,
        },
        "languages": list(checked_languages),
        "sample_count": len(rows),
        "candidates": candidates,
    }


def main() -> None:
    # 重型依赖延迟到真实运行入口加载；导入纯比较逻辑时不加载 FunASR。
    from src.asr.factory import create_asr_backend

    project_root = Path(__file__).resolve().parents[1]
    default_dir = project_root / "evaluation" / "asr_commands"

    parser = argparse.ArgumentParser(
        description="比较固定命令 WAV 的 language=auto 与 language=zh。"
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=default_dir / "manifest.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_dir / "language_comparison.json",
    )
    parser.add_argument(
        "--languages",
        nargs="+",
        default=["auto", "zh"],
    )
    args = parser.parse_args()

    languages = validate_languages(args.languages)
    rows = load_manifest(args.manifest)
    report = compare_languages(
        rows,
        recognizer=create_asr_backend(),
        languages=languages,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for language in languages:
        metrics = report["candidates"][language]["metrics"]
        print(
            f"{language}: 文本精确 "
            f"{metrics['exact_text_match_count']}/"
            f"{metrics['labeled_text_sample_count']}，意图命中 "
            f"{metrics['intent_match_count']}/"
            f"{metrics['intent_sample_count']}"
        )
    print(f"对照报告已保存：{args.output}")


if __name__ == "__main__":
    main()
