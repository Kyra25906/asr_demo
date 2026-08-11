"""使用固定非敏感文本验收正式统一理解Processor。"""

from __future__ import annotations

from dataclasses import dataclass

from src.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_ATTEMPTS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_RETRY_DELAY_SECONDS,
    LLM_TIMEOUT_SECONDS,
)
from src.core.interaction_command import InteractionCommandType
from src.core.unified_understanding import (
    UnifiedInputKind,
    UnifiedUnderstandingInput,
)
from src.llm.client import OpenAICompatibleLLMClient
from src.llm.unified_processor import UnifiedUnderstandingProcessor


@dataclass(frozen=True)
class UnifiedSmokeCase:
    name: str
    text: str
    expected_kind: UnifiedInputKind
    expected_command: InteractionCommandType | None = None
    pending_numbers: tuple[int, ...] = ()
    current_number: int | None = None


CASES = (
    UnifiedSmokeCase(
        "普通实验口述",
        "加入五毫升缓冲液并搅拌。",
        UnifiedInputKind.EXPERIMENT,
    ),
    UnifiedSmokeCase(
        "自然查看问题",
        "我还有什么没有回答？",
        UnifiedInputKind.CONTROL,
        InteractionCommandType.REVIEW_PENDING,
        (1, 2),
        2,
    ),
    UnifiedSmokeCase(
        "自然结束候选",
        "今天先记录到这里吧。",
        UnifiedInputKind.CONTROL,
        InteractionCommandType.END_SESSION,
    ),
    UnifiedSmokeCase(
        "语义不足时弃权",
        "这个差不多了。",
        UnifiedInputKind.UNCERTAIN,
    ),
    UnifiedSmokeCase(
        "指定问题答复候选",
        "关于第二个，是五分钟。",
        UnifiedInputKind.CONTROL,
        InteractionCommandType.TARGETED_ANSWER,
        (1, 2),
        2,
    ),
)


def build_processor() -> UnifiedUnderstandingProcessor:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY为空，请检查项目根目录.env。")
    return UnifiedUnderstandingProcessor(OpenAICompatibleLLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        max_tokens=LLM_MAX_TOKENS,
        max_attempts=LLM_MAX_ATTEMPTS,
        retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    ))


def result_matches(case: UnifiedSmokeCase, outcome) -> bool:
    if outcome.degraded or outcome.value.input_kind != case.expected_kind:
        return False
    if case.expected_kind == UnifiedInputKind.CONTROL:
        return (
            outcome.value.control.intent.command_type
            == case.expected_command
        )
    return case.expected_command is None


def main() -> None:
    processor = build_processor()
    passed = 0

    print("DeepSeek正式统一理解烟雾测试")
    print(f"模型：{LLM_MODEL}")
    print("API Key：已加载，不显示内容")
    print("模型逐条原始响应：不打印、不保存")

    for index, case in enumerate(CASES, start=1):
        outcome = processor.understand(UnifiedUnderstandingInput(
            raw_text=case.text,
            session_active=True,
            session_id="unified_real_smoke",
            segment_id=index,
            pending_question_numbers=case.pending_numbers,
            current_question_number=case.current_number,
        ))
        matched = result_matches(case, outcome)
        passed += int(matched)

        command = (
            outcome.value.control.intent.command_type.value
            if outcome.value.control is not None
            else None
        )
        print(f"\n[{index}] {case.name}")
        print(f"输入：{case.text}")
        print(f"分支：{outcome.value.input_kind.value}")
        print(f"控制候选：{command}")
        print(f"是否降级：{outcome.degraded}")
        print(f"尝试次数：{outcome.llm_attempts}")
        print(f"模型耗时：{outcome.llm_processing_seconds:.3f}秒")
        if outcome.error:
            print(f"错误：{outcome.error}")
        print(f"结果：{'通过' if matched else '不符合预期'}")

    print(f"\n汇总：{passed}/{len(CASES)}条符合预期")
    if passed != len(CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
