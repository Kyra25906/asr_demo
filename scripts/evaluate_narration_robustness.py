"""对ASR鲁棒性口述语料运行统一理解链评测。

--mode deterministic（默认）：只用精确命令解析器（零LLM快速路径）逐段报告
  行为归类，输出 evaluation/narration_robustness/deterministic_report.json。
--mode real：把模拟ASR噪声转写真实发给DeepSeek统一理解，输出
  "期望 vs 实际"对照报告（只读，不写业务数据，不打印/保存模型原始响应）。

运行方式（在项目根目录）：
  .\\.venv\\Scripts\\python.exe -B -m scripts.evaluate_narration_robustness --mode deterministic
  .\\.venv\\Scripts\\python.exe -B -m scripts.evaluate_narration_robustness --mode real
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_ATTEMPTS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_RETRY_DELAY_SECONDS,
    LLM_TIMEOUT_SECONDS,
)
from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.unified_understanding import UnifiedUnderstandingInput
from src.evaluation.narration_robustness_plan import NarrationRobustnessPlan
from src.llm.client import OpenAICompatibleLLMClient
from src.llm.unified_processor import UnifiedUnderstandingProcessor

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "narration_robustness"
    / "narration_plan.json"
)
DETERMINISTIC_REPORT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "narration_robustness"
    / "deterministic_report.json"
)
REAL_REPORT_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "narration_robustness"
    / "real_report.json"
)


def classify_exact_row(
    segment,
    exact: InteractionCommand,
) -> dict:
    """把精确解析器行为归类为：零误触发 / 精确命中 / 依赖LLM / 已知限制。"""

    exact_type = exact.command_type
    category = "依赖LLM容错"
    detail = "精确解析为normal，需LLM语义容错"
    if segment.expected_input_kind == "experiment":
        if exact_type != InteractionCommandType.NORMAL:
            category = "误触发缺口"
            detail = (
                f"实验段被精确解析为{exact_type.value}，属于误触发"
            )
        else:
            category = "零误触发"
            detail = "实验段不触发任何控制命令"
    else:
        if segment.challenge_type == "answer_two_in_one":
            category = "已知限制"
            detail = (
                f"整句被当问题{exact.target_question_number}的答案，"
                "第二个问题拼入answer_text"
            )
        elif segment.challenge_type == "answer_number_only":
            category = "已知限制"
            detail = "只有编号无答案内容，下游应转no_action"
        elif segment.challenge_type == "answer_wrong_number":
            category = "已知限制"
            detail = (
                f"编号{exact.target_question_number}不在待确认列表，"
                "下游应no_action或提醒"
            )
        elif (
            segment.expected_command is not None
            and exact_type.value == segment.expected_command
        ):
            category = "精确命中"
            detail = "零LLM快速路径命中"
        else:
            category = "依赖LLM容错"
            detail = "精确解析为normal，需LLM语义容错"
    return {
        "segment_id": segment.segment_id,
        "challenge_type": segment.challenge_type,
        "observed_asr_text": segment.observed_asr_text,
        "exact_command": exact_type.value,
        "exact_target_question_number": (
            exact.target_question_number
            if exact_type == InteractionCommandType.TARGETED_ANSWER
            else None
        ),
        "category": category,
        "detail": detail,
    }


def run_deterministic(plan: NarrationRobustnessPlan) -> dict:
    rows = []
    for segment in plan.segments:
        command = InteractionCommandParser.parse(segment.observed_asr_text)
        rows.append(classify_exact_row(segment, command))

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1

    report = {
        "session_id": plan.session_id,
        "schema_version": plan.schema_version,
        "segment_count": len(rows),
        "categories": counts,
        "rows": rows,
    }
    DETERMINISTIC_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def run_real(plan: NarrationRobustnessPlan) -> dict:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY为空，请检查项目根目录.env。")
    processor = UnifiedUnderstandingProcessor(OpenAICompatibleLLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        max_tokens=LLM_MAX_TOKENS,
        max_attempts=LLM_MAX_ATTEMPTS,
        retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    ))

    rows = []
    for index, segment in enumerate(plan.segments, start=1):
        recent_context = tuple(
            plan.segments[previous].observed_asr_text
            for previous in range(max(0, index - 3), index - 1)
        )
        outcome = processor.understand(UnifiedUnderstandingInput(
            raw_text=segment.observed_asr_text,
            session_active=True,
            session_id=plan.session_id,
            segment_id=index,
            recent_context=recent_context,
            pending_question_numbers=segment.pending_question_numbers,
            current_question_number=segment.current_question_number,
        ))
        rows.append(_build_real_row(segment, outcome))

    passed = sum(1 for row in rows if row["consistent"])
    report = {
        "session_id": plan.session_id,
        "model": LLM_MODEL,
        "segment_count": len(rows),
        "consistent_count": passed,
        "gap_count": len(rows) - passed,
        "rows": rows,
    }
    REAL_REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _build_real_row(segment, outcome) -> dict:
    value = outcome.value
    actual_kind = value.input_kind.value
    actual_command = None
    actual_missing: list[str] = []
    actual_confirmation = False
    actual_follow_up = False
    follow_up_question = None

    if value.experiment is not None:
        analysis = value.experiment.analysis
        actual_follow_up = analysis.should_ask_follow_up
        follow_up_question = analysis.follow_up_question
        seen_missing: list[str] = []
        for event in analysis.events:
            for field in event.missing_fields:
                if field not in seen_missing:
                    seen_missing.append(field)
            if event.needs_confirmation:
                actual_confirmation = True
        actual_missing = seen_missing
    elif value.control is not None:
        actual_command = value.control.intent.command_type.value

    expected_missing = set(segment.expected_missing_fields)
    actual_missing_set = set(actual_missing)

    kind_ok = actual_kind == segment.expected_input_kind
    command_ok = (
        actual_command == segment.expected_command
        if segment.expected_input_kind == "control"
        else True
    )
    missing_ok = expected_missing.issubset(actual_missing_set)
    confirmation_ok = (
        actual_confirmation == segment.expected_needs_confirmation
    )
    consistent = kind_ok and command_ok and missing_ok and confirmation_ok

    return {
        "segment_id": segment.segment_id,
        "challenge_type": segment.challenge_type,
        "observed_asr_text": segment.observed_asr_text,
        "expected_input_kind": segment.expected_input_kind,
        "expected_command": segment.expected_command,
        "expected_missing_fields": segment.expected_missing_fields,
        "expected_needs_confirmation": segment.expected_needs_confirmation,
        "actual_input_kind": actual_kind,
        "actual_command": actual_command,
        "actual_missing_fields": actual_missing,
        "actual_needs_confirmation": actual_confirmation,
        "actual_follow_up": actual_follow_up,
        "follow_up_question": follow_up_question,
        "degraded": outcome.degraded,
        "kind_ok": kind_ok,
        "command_ok": command_ok,
        "missing_ok": missing_ok,
        "confirmation_ok": confirmation_ok,
        "consistent": consistent,
    }


def print_deterministic(report: dict) -> None:
    print("ASR鲁棒性语料 · 精确解析器行为报告（确定性，零外部调用）")
    print(f"语料：{report['session_id']}，共 {report['segment_count']} 段")
    print(f"归类统计：{report['categories']}")
    for row in report["rows"]:
        print(
            f"  [{row['segment_id']:>2}] {row['challenge_type']:<24} "
            f"精确={row['exact_command']:<15} "
            f"{row['category']}：{row['detail']}"
        )
    print(f"报告已保存：{DETERMINISTIC_REPORT_PATH}")


def print_real(report: dict) -> None:
    print("ASR鲁棒性语料 · 真实DeepSeek统一理解对照报告（只读旁路）")
    print(
        f"模型：{report['model']}；"
        f"一致 {report['consistent_count']}/{report['segment_count']}，"
        f"缺口 {report['gap_count']}"
    )
    for row in report["rows"]:
        marker = "一致" if row["consistent"] else "缺口"
        print(f"\n[{row['segment_id']:>2}] {row['challenge_type']} -> {marker}")
        print(f"  转写：{row['observed_asr_text']}")
        print(
            f"  期望：kind={row['expected_input_kind']} "
            f"command={row['expected_command']} "
            f"missing={row['expected_missing_fields']} "
            f"confirm={row['expected_needs_confirmation']}"
        )
        print(
            f"  实际：kind={row['actual_input_kind']} "
            f"command={row['actual_command']} "
            f"missing={row['actual_missing_fields']} "
            f"confirm={row['actual_needs_confirmation']} "
            f"追问={row['follow_up_question']}"
        )
        print(f"  降级：{row['degraded']}")
    print(f"报告已保存：{REAL_REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ASR鲁棒性口述语料统一理解链评测。"
    )
    parser.add_argument(
        "--mode",
        choices=("deterministic", "real"),
        default="deterministic",
    )
    args = parser.parse_args()

    plan = NarrationRobustnessPlan.load(PLAN_PATH)
    if args.mode == "deterministic":
        report = run_deterministic(plan)
        print_deterministic(report)
        return

    report = run_real(plan)
    print_real(report)


if __name__ == "__main__":
    main()
