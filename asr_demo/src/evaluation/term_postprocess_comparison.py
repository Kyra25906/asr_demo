"""比较原始ASR文本与术语后处理候选，不覆盖原始结果。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, Sequence

from scripts.evaluate_asr_commands import evaluate_manifest


class TextCorrector(Protocol):
    def apply_text(self, text: str): ...


def compare_term_postprocess(
    rows: Sequence[dict[str, Any]],
    *,
    corrector: TextCorrector,
    target_terms: Sequence[str],
    threshold: float,
) -> dict[str, Any]:
    """计算候选后处理的改善、回退和术语命中。"""

    terms = tuple(term.strip() for term in target_terms)
    if not terms or any(not term for term in terms):
        raise ValueError("target_terms必须包含非空术语。")
    if len(set(terms)) != len(terms):
        raise ValueError("target_terms不能重复。")

    baseline_rows = [deepcopy(row) for row in rows]
    candidate_rows: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for row in baseline_rows:
        corrected, matches = corrector.apply_text(row["observed_asr_text"])
        candidate = deepcopy(row)
        candidate["observed_asr_text"] = corrected
        candidate_rows.append(candidate)
        if matches:
            changes.append({
                "sample_id": row["sample_id"],
                "original_text": row["observed_asr_text"],
                "candidate_text": corrected,
                "matches": [
                    match.as_dict() if hasattr(match, "as_dict") else match
                    for match in matches
                ],
            })

    baseline = evaluate_manifest(baseline_rows)
    candidate = evaluate_manifest(candidate_rows)
    baseline_details = {item["sample_id"]: item for item in baseline["details"]}
    candidate_details = {item["sample_id"]: item for item in candidate["details"]}

    text_improvements = []
    text_regressions = []
    intent_improvements = []
    intent_regressions = []
    for sample_id in baseline_details:
        before = baseline_details[sample_id]
        after = candidate_details[sample_id]
        if before["text_match"] is False and after["text_match"] is True:
            text_improvements.append(sample_id)
        if before["text_match"] is True and after["text_match"] is False:
            text_regressions.append(sample_id)
        if not before["intent_match"] and after["intent_match"]:
            intent_improvements.append(sample_id)
        if before["intent_match"] and not after["intent_match"]:
            intent_regressions.append(sample_id)

    term_cases = 0
    baseline_term_hits = 0
    candidate_term_hits = 0
    for source, corrected in zip(baseline_rows, candidate_rows, strict=True):
        for term in terms:
            if term not in source["reference_text"]:
                continue
            term_cases += 1
            baseline_term_hits += int(term in source["observed_asr_text"])
            candidate_term_hits += int(term in corrected["observed_asr_text"])

    return {
        "schema_version": 1,
        "experiment": "sensevoice_term_postprocess_comparison",
        "target_terms": list(terms),
        "threshold": threshold,
        "sample_count": len(rows),
        "baseline_metrics": baseline,
        "candidate_metrics": candidate,
        "target_term_case_count": term_cases,
        "baseline_target_term_hit_count": baseline_term_hits,
        "candidate_target_term_hit_count": candidate_term_hits,
        "changed_sample_count": len(changes),
        "changes": changes,
        "text_improvements": text_improvements,
        "text_regressions": text_regressions,
        "intent_improvements": intent_improvements,
        "intent_regressions": intent_regressions,
    }
