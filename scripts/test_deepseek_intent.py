"""使用固定非敏感文本验收真实DeepSeek意图分类。"""

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
from src.core.intent_classifier import (
    IntentCandidateStatus,
    IntentClassificationInput,
)
from src.core.intent_policy import (
    IntentDisposition,
    IntentPolicyEvaluator,
)
from src.core.interaction_command import InteractionCommandType
from src.llm.client import OpenAICompatibleLLMClient
from src.llm.intent_classifier import LLMIntentClassifier


@dataclass(frozen=True)
class SmokeCase:
    name: str
    text: str
    expected_status: IntentCandidateStatus
    expected_command: InteractionCommandType | None
    expected_disposition: IntentDisposition
    pending_numbers: tuple[int, ...] = ()
    current_number: int | None = None


CASES = (
    SmokeCase(
        name="普通实验口述",
        text="加入五毫升缓冲液并搅拌。",
        expected_status=IntentCandidateStatus.MATCHED,
        expected_command=InteractionCommandType.NORMAL,
        expected_disposition=IntentDisposition.PASS_TO_EXPERIMENT,
    ),
    SmokeCase(
        name="自然查看问题",
        text="我还有什么没有回答？",
        expected_status=IntentCandidateStatus.MATCHED,
        expected_command=InteractionCommandType.REVIEW_PENDING,
        expected_disposition=IntentDisposition.REQUIRE_CONTEXT,
        pending_numbers=(1, 2),
        current_number=2,
    ),
    SmokeCase(
        name="自然结束候选",
        text="今天先记录到这里吧。",
        expected_status=IntentCandidateStatus.MATCHED,
        expected_command=InteractionCommandType.END_SESSION,
        expected_disposition=IntentDisposition.REQUEST_CONFIRMATION,
    ),
    SmokeCase(
        name="语义不足时弃权",
        text="这个差不多了。",
        expected_status=IntentCandidateStatus.UNCERTAIN,
        expected_command=None,
        expected_disposition=IntentDisposition.PASS_TO_EXPERIMENT,
    ),
    SmokeCase(
        name="指定问题答复候选",
        text="关于第二个，是五分钟。",
        expected_status=IntentCandidateStatus.MATCHED,
        expected_command=InteractionCommandType.TARGETED_ANSWER,
        expected_disposition=IntentDisposition.DO_NOT_EXECUTE,
        pending_numbers=(1, 2),
        current_number=2,
    ),
)


def build_classifier() -> LLMIntentClassifier:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY为空，请检查项目根目录.env。"
        )
    client = OpenAICompatibleLLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        timeout_seconds=LLM_TIMEOUT_SECONDS,
        max_tokens=LLM_MAX_TOKENS,
        max_attempts=LLM_MAX_ATTEMPTS,
        retry_delay_seconds=LLM_RETRY_DELAY_SECONDS,
    )
    return LLMIntentClassifier(client)


def main() -> None:
    classifier = build_classifier()
    passed = 0

    print("DeepSeek意图分类烟雾测试")
    print(f"模型：{LLM_MODEL}")
    print("API Key：已加载，不显示内容")

    for index, case in enumerate(CASES, start=1):
        request = IntentClassificationInput(
            raw_text=case.text,
            session_active=True,
            pending_question_numbers=case.pending_numbers,
            current_question_number=case.current_number,
        )
        try:
            result = classifier.classify_with_metrics(request)
            candidate = result.candidate
            command = candidate.command_type
            disposition = (
                IntentPolicyEvaluator.evaluate(
                    command,
                    candidate.evidence,
                ).disposition
                if command is not None
                else IntentDisposition.PASS_TO_EXPERIMENT
            )
            matched = (
                candidate.status == case.expected_status
                and command == case.expected_command
                and disposition == case.expected_disposition
            )
            passed += int(matched)

            print(f"\n[{index}] {case.name}")
            print(f"输入：{case.text}")
            print(f"status：{candidate.status.value}")
            print(
                "command_type："
                f"{command.value if command else None}"
            )
            print(f"策略出口：{disposition.value}")
            print(f"尝试次数：{result.attempts}")
            print(f"模型耗时：{result.processing_seconds:.3f}秒")
            print(f"结果：{'通过' if matched else '不符合预期'}")
        except Exception as error:
            print(f"\n[{index}] {case.name}")
            print(f"结果：失败，{type(error).__name__}: {error}")

    print(f"\n汇总：{passed}/{len(CASES)}条符合预期")
    if passed != len(CASES):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
