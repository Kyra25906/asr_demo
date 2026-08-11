"""比较独立意图分类与统一实验理解调用。"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from statistics import mean

from src.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_ATTEMPTS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_RETRY_DELAY_SECONDS,
    LLM_TIMEOUT_SECONDS,
)
from src.core.intent_classifier import (
    IntentCandidate,
    IntentClassificationInput,
)
from src.core.interaction_command import InteractionCommandType
from src.llm.client import OpenAICompatibleLLMClient
from src.llm.intent_classifier import LLMIntentClassifier
from src.llm.processor import ExperimentLLMProcessor
from src.llm.validation import parse_analysis


FIXED_TEXT = "加入五毫升缓冲液并搅拌。"

UNIFIED_SYSTEM_PROMPT = """\
你是实验语音智能体的统一输入理解器。只输出一个JSON对象，不得输出其他文字。

先判断输入是实验内容、控制意图还是无法确定：
- experiment：实验操作、观察、测量、异常或其他实验事实。
- control：查看问题、暂缓问题、肯定、否定、指定回答或结束会话。
- uncertain：无法可靠区分实验内容和控制意图。

顶层必须且只能包含：
{
  "input_kind": "experiment | control | uncertain",
  "intent": "控制候选对象或null",
  "analysis": "实验分析对象或null"
}

control时intent使用以下严格结构，analysis必须为null：
{
  "status": "matched",
  "command_type": "review_pending | defer_current | affirm | deny | targeted_answer | end_session",
  "target_question_number": "正整数或null",
  "answer_text": "用户明确答复或null",
  "reason": "简短原因或null"
}

uncertain时analysis必须为null，intent必须为：
{
  "status": "uncertain",
  "command_type": null,
  "target_question_number": null,
  "answer_text": null,
  "reason": "简短原因或null"
}

experiment时intent必须为null，analysis必须严格为：
{
  "events": [{
    "event_type": "operation | observation | measurement | anomaly | note",
    "raw_text": "逐字复制本轮ASR原文",
    "normalized_text": "不改变事实的规范表达",
    "entities": {
      "action": "字符串或null", "object": "字符串或null",
      "instrument": "字符串或null", "amount_value": "字符串或null",
      "amount_unit": "字符串或null", "concentration": "字符串或null",
      "temperature": "字符串或null", "duration": "字符串或null",
      "condition": "字符串或null", "observation": "字符串或null"
    },
    "missing_fields": ["字段名"],
    "needs_confirmation": false,
    "confirmation_reason": "字符串或null"
  }],
  "should_ask_follow_up": false,
  "follow_up_question": "字符串或null",
  "assistant_reply": "字符串或null"
}

实验分析规则：
- 每个event.raw_text必须逐字等于本轮ASR原文。
- 上下文只用于理解，不得把旧事实重复输出为本轮事件。
- 不得猜测、补造或换算数值和单位。
- needs_confirmation=true或任何missing_fields非空时，should_ask_follow_up必须为true且follow_up_question非空。
- 所有event都不需要确认且missing_fields都为空时，should_ask_follow_up必须为false且follow_up_question为null。
- source_session_id和source_segment_id由程序注入，模型不得输出。
- 禁止任何未声明字段。

不得猜测或覆盖ASR原文；无法可靠判断input_kind时返回uncertain。
"""


@dataclass(frozen=True)
class UnifiedResult:
    input_kind: str
    intent: IntentCandidate | None
    event_count: int


def build_unified_user_prompt(raw_text: str) -> str:
    return json.dumps(
        {
            "recent_context": [],
            "current_asr_raw_text": raw_text,
            "session_active": True,
            "pending_question_numbers": [],
            "current_question_number": None,
        },
        ensure_ascii=False,
    )


def parse_unified_response(
    content: str,
    *,
    raw_text: str,
    segment_id: int,
) -> UnifiedResult:
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("统一响应顶层必须是对象。")
    expected = {"input_kind", "intent", "analysis"}
    if set(data) != expected:
        raise ValueError("统一响应顶层字段不严格匹配。")

    kind = data["input_kind"]
    if kind == "experiment":
        if data["intent"] is not None or not isinstance(
            data["analysis"], dict
        ):
            raise ValueError("experiment的intent/analysis组合非法。")
        analysis = parse_analysis(
            json.dumps(data["analysis"], ensure_ascii=False),
            expected_raw_text=raw_text,
            session_id="architecture_comparison",
            segment_id=segment_id,
        )
        return UnifiedResult(kind, None, len(analysis.events))

    if kind in {"control", "uncertain"}:
        if data["analysis"] is not None or not isinstance(
            data["intent"], dict
        ):
            raise ValueError(f"{kind}的intent/analysis组合非法。")
        candidate = IntentCandidate.from_mapping(data["intent"])
        if kind == "control" and candidate.command_type is None:
            raise ValueError("control必须包含命令类型。")
        if kind == "uncertain" and candidate.command_type is not None:
            raise ValueError("uncertain不能包含命令类型。")
        return UnifiedResult(kind, candidate, 0)

    raise ValueError(f"不支持的input_kind：{kind!r}")


def build_client():
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY为空，请检查.env。")
    return OpenAICompatibleLLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        max_tokens=LLM_MAX_TOKENS,
        max_attempts=LLM_MAX_ATTEMPTS,
        retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    if args.trials <= 0:
        raise SystemExit("--trials必须大于0")

    client = build_client()
    classifier = LLMIntentClassifier(client)
    processor = ExperimentLLMProcessor(client)
    independent_times = []
    unified_times = []
    failed_trials = []

    print(f"模型：{LLM_MODEL}")
    print(f"固定输入：{FIXED_TEXT}")
    print(f"重复轮数：{args.trials}")

    for trial in range(1, args.trials + 1):
        try:
            classification = classifier.classify_with_metrics(
                request=IntentClassificationInput(
                    raw_text=FIXED_TEXT,
                    session_active=True,
                )
            )
            if (
                classification.candidate.command_type
                != InteractionCommandType.NORMAL
            ):
                raise RuntimeError("独立分类未返回normal。")
            analysis = processor.analyze_segment(
                raw_text=FIXED_TEXT,
                session_id="architecture_comparison",
                segment_id=trial,
            )
            if analysis.degraded:
                raise RuntimeError(f"独立结构化降级：{analysis.error}")
            independent = (
                classification.processing_seconds
                + analysis.llm_processing_seconds
            )

            generation = client.generate_json(
                system_prompt=UNIFIED_SYSTEM_PROMPT,
                user_prompt=build_unified_user_prompt(FIXED_TEXT),
            )
            unified_result = parse_unified_response(
                generation.content,
                raw_text=FIXED_TEXT,
                segment_id=trial,
            )
            if unified_result.input_kind != "experiment":
                raise RuntimeError("统一调用未返回experiment。")

            independent_times.append(independent)
            unified_times.append(generation.processing_seconds)
            print(
                f"第{trial}轮：独立两次={independent:.3f}秒，"
                f"统一一次={generation.processing_seconds:.3f}秒"
            )
        except Exception as error:
            failed_trials.append(trial)
            print(
                f"第{trial}轮失败："
                f"{type(error).__name__}: {error}"
            )

    if not independent_times:
        raise SystemExit("没有获得任何完整配对，无法比较。")
    independent_average = mean(independent_times)
    unified_average = mean(unified_times)
    saved = independent_average - unified_average
    print(f"\n独立两次平均：{independent_average:.3f}秒")
    print(f"统一一次平均：{unified_average:.3f}秒")
    print(f"平均节省：{saved:.3f}秒")
    print(
        "相对减少："
        f"{saved / independent_average * 100:.1f}%"
    )
    print(f"完整配对：{len(independent_times)}/{args.trials}")
    if failed_trials:
        print(f"失败轮次：{failed_trials}")


if __name__ == "__main__":
    main()
