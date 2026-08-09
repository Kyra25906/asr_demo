"""识别24条accepted控制命令WAV并生成本地新基线。"""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.command_corpus_baseline import (
    build_capture_baseline,
    load_accepted_attempts,
)
from src.evaluation.command_corpus_plan import CommandCorpusPlan


def main() -> None:
    from src.asr.recognizer import SpeechRecognizer

    project_root = Path(__file__).resolve().parents[1]
    corpus_dir = project_root / "evaluation" / "asr_commands"
    plan = CommandCorpusPlan.load(corpus_dir / "capture_plan.json")
    accepted = load_accepted_attempts(corpus_dir / "capture_attempts.jsonl")
    rows, metrics = build_capture_baseline(
        plan, accepted, recognizer=SpeechRecognizer(), language="auto"
    )

    manifest_path = corpus_dir / "captured_manifest.jsonl"
    baseline_path = corpus_dir / "captured_baseline.json"
    manifest_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n" for row in rows
        ),
        encoding="utf-8",
    )
    baseline_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"样本数：{metrics['sample_count']}")
    print(
        "文本精确率："
        f"{metrics['exact_text_match_count']}/"
        f"{metrics['labeled_text_sample_count']}"
    )
    print(
        "命令意图准确率："
        f"{metrics['intent_match_count']}/"
        f"{metrics['intent_sample_count']}"
    )
    print(f"控制命令漏触发：{metrics['control_command_miss_count']}")
    print(f"精确规则覆盖不足：{metrics['rule_coverage_miss_count']}")
    print(
        "ASR额外造成意图漏触发："
        f"{metrics['asr_induced_intent_miss_count']}"
    )
    print(
        "普通内容误触发："
        f"{metrics['normal_content_false_trigger_count']}"
    )
    print(f"新清单：{manifest_path}")
    print(f"新基线：{baseline_path}")


if __name__ == "__main__":
    main()
