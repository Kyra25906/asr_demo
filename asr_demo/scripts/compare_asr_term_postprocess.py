"""对已保存的24条ASR原文运行术语后处理候选对照。"""

from __future__ import annotations

import json
from pathlib import Path

from funasr.utils.postprocess_hotwords import PostprocessHotwordMatcher

from src.evaluation.term_postprocess_comparison import (
    compare_term_postprocess,
)


TARGET_TERMS = ("移液枪", "水浴", "滴定管")
THRESHOLD = 0.85


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    corpus_dir = project_root / "evaluation" / "asr_commands"
    manifest_path = corpus_dir / "captured_manifest.jsonl"
    output_path = corpus_dir / "term_postprocess_comparison.json"
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matcher = PostprocessHotwordMatcher(
        fuzzy_targets=TARGET_TERMS,
        threshold=THRESHOLD,
    )
    report = compare_term_postprocess(
        rows,
        corrector=matcher,
        target_terms=TARGET_TERMS,
        threshold=THRESHOLD,
    )
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    before = report["baseline_metrics"]
    after = report["candidate_metrics"]
    print(f"样本数：{report['sample_count']}")
    print(f"修改样本：{report['changed_sample_count']}")
    print(
        "目标术语命中："
        f"{report['baseline_target_term_hit_count']}/"
        f"{report['target_term_case_count']} → "
        f"{report['candidate_target_term_hit_count']}/"
        f"{report['target_term_case_count']}"
    )
    print(
        "严格文本精确："
        f"{before['exact_text_match_count']}/24 → "
        f"{after['exact_text_match_count']}/24"
    )
    print(
        "意图命中："
        f"{before['intent_match_count']}/24 → "
        f"{after['intent_match_count']}/24"
    )
    print(f"文本改善：{report['text_improvements']}")
    print(f"文本回退：{report['text_regressions']}")
    print(f"意图回退：{report['intent_regressions']}")
    print(f"本地报告：{output_path}")


if __name__ == "__main__":
    main()
