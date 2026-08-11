import json
import unittest

from src.core.intent_policy import (
    IntentDisposition,
    IntentEvidence,
)
from src.core.intent_router import IntentRouter
from src.core.interaction_command import InteractionCommandType
from src.llm.client import LLMClientError, LLMGenerationResult
from src.llm.intent_classifier import LLMIntentClassifier


class FakeLLMClient:
    """模块集成测试使用的通用LLM客户端替身。"""

    def __init__(self, *, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def generate_json(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if self.error is not None:
            raise self.error
        return LLMGenerationResult(
            content=self.content,
            attempts=1,
            processing_seconds=0.1,
        )


def response_json(
    *,
    status="matched",
    command_type="normal",
    target_question_number=None,
    answer_text=None,
    reason=None,
):
    return json.dumps({
        "status": status,
        "command_type": command_type,
        "target_question_number": target_question_number,
        "answer_text": answer_text,
        "reason": reason,
    }, ensure_ascii=False)


def build_router(client):
    return IntentRouter(
        classifier=LLMIntentClassifier(client),
    )


class LLMIntentRouterIntegrationTests(unittest.TestCase):
    def test_exact_command_skips_entire_llm_chain(self):
        client = FakeLLMClient(
            error=AssertionError("精确命令不应调用LLM"),
        )

        result = build_router(client).route("结束实验记录。")

        self.assertEqual(client.calls, [])
        self.assertFalse(result.classifier_used)
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.EXECUTE,
        )

    def test_natural_review_reaches_low_risk_context_route(self):
        client = FakeLLMClient(content=response_json(
            command_type="review_pending",
            reason="用户希望查看未解决的问题。",
        ))

        result = build_router(client).route(
            "我还有什么没有回答？",
            pending_question_numbers=(1, 2),
            current_question_number=2,
        )

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(
            result.decision.evidence,
            IntentEvidence.LLM_CANDIDATE,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )

    def test_natural_end_never_executes_directly(self):
        client = FakeLLMClient(content=response_json(
            command_type="end_session",
            reason="用户可能希望结束本次记录。",
        ))

        result = build_router(client).route("今天先记到这里吧。")

        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUEST_CONFIRMATION,
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_uncertain_result_abstains_and_keeps_raw_text(self):
        raw_text = "这个差不多了。"
        client = FakeLLMClient(content=response_json(
            status="uncertain",
            command_type=None,
            reason="含义不足以区分操作完成和会话结束。",
        ))

        result = build_router(client).route(raw_text)

        self.assertEqual(result.raw_text, raw_text)
        self.assertTrue(result.classification_uncertain)
        self.assertTrue(result.is_experiment_text)
        self.assertFalse(result.decision.may_execute_now)

    def test_malformed_model_output_degrades_without_control_action(self):
        client = FakeLLMClient(content="not-json")

        result = build_router(client).route("我想看看问题。")

        self.assertTrue(result.classifier_used)
        self.assertTrue(result.is_experiment_text)
        self.assertIn("IntentClassifierError", result.classification_error)
        self.assertFalse(result.decision.may_execute_now)

    def test_client_failure_degrades_without_control_action(self):
        error = LLMClientError(
            "timeout",
            attempts=2,
            processing_seconds=1.5,
        )
        client = FakeLLMClient(error=error)

        result = build_router(client).route("我想看看问题。")

        self.assertEqual(
            result.classification_error,
            "LLMClientError: timeout",
        )
        self.assertTrue(result.is_experiment_text)
        self.assertFalse(result.decision.may_execute_now)

    def test_normal_experiment_text_continues_to_experiment_route(self):
        raw_text = "加入五毫升缓冲液并搅拌。"
        client = FakeLLMClient(content=response_json(
            command_type="normal",
            reason="用户正在描述实验操作。",
        ))

        result = build_router(client).route(raw_text)

        self.assertEqual(result.raw_text, raw_text)
        self.assertTrue(result.classifier_used)
        self.assertTrue(result.is_experiment_text)
        self.assertIsNone(result.classification_error)


if __name__ == "__main__":
    unittest.main()
