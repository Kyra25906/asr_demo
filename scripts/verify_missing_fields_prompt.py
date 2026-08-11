"""验证统一Prompt缺失字段检测：将溶液加热 → missing_fields=(temperature, duration)"""

from __future__ import annotations

import json

from src.core.unified_understanding import UnifiedUnderstandingInput
from src.llm.factory import create_llm_client
from src.llm.unified_processor import UnifiedUnderstandingProcessor


def main() -> None:
    print("真实DeepSeek复验：将溶液加热 → missing_fields")
    print("原始响应：不打印，不保存\n")

    text = "将溶液加热。"

    client = create_llm_client()
    processor = UnifiedUnderstandingProcessor(client)

    request = UnifiedUnderstandingInput(
        raw_text=text,
        session_active=True,
        session_id="verify-missing-fields",
        segment_id=1,
    )

    outcome = processor.understand(request)

    print(f"降级: {outcome.degraded}")
    print(f"LLM尝试次数: {outcome.llm_attempts}")
    print(f"LLM处理秒数: {outcome.llm_processing_seconds}")

    if outcome.value.experiment:
        analysis = outcome.value.experiment.analysis
        print(f"\n实验事件数: {len(analysis.events)}")
        for i, event in enumerate(analysis.events):
            print(f"\n  事件{i + 1}:")
            print(f"    event_type: {event.event_type.value}")
            print(f"    normalized_text: {event.normalized_text}")
            print(f"    missing_fields: {event.missing_fields}")
            print(f"    needs_confirmation: {event.needs_confirmation}")
        print(f"\n  should_ask_follow_up: {analysis.should_ask_follow_up}")
        print(f"  follow_up_question: {analysis.follow_up_question}")
    elif outcome.value.control:
        print(f"\n控制分支: {outcome.value.control.intent.command_type}")
    elif outcome.value.uncertain:
        print(f"\n弃权: {outcome.value.uncertain.reason}")

    target = ("temperature" in str(analysis.events[0].missing_fields)
              and "duration" in str(analysis.events[0].missing_fields)
              and analysis.should_ask_follow_up)

    print(f"\n{'✓ 验收通过' if target else '✗ 验收未通过'}")

    # Also print the raw analysis as debug
    if outcome.value.experiment:
        print("\n--- 事件详情(JSON) ---")
        for event in analysis.events:
            print(json.dumps({
                "event_type": event.event_type.value,
                "raw_text": event.raw_text,
                "normalized_text": event.normalized_text,
                "entities": {k: v for k, v in event.entities.__dict__.items()},
                "missing_fields": event.missing_fields,
                "needs_confirmation": event.needs_confirmation,
                "confirmation_reason": event.confirmation_reason,
            }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
