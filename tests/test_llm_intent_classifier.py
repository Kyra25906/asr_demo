import json
import unittest

from src.core.intent_classifier import (
    IntentCandidateStatus,
    IntentClassificationInput,
    IntentClassifierError,
)
from src.core.interaction_command import InteractionCommandType
from src.llm.client import LLMClientError, LLMGenerationResult
from src.llm.intent_classifier import LLMIntentClassifier


class FakeLLMClient:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def generate_json(self, *, system_prompt, user_prompt):
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        })
        if self.error is not None:
            raise self.error
        return LLMGenerationResult(
            content=self.content,
            attempts=1,
            processing_seconds=0.1,
        )


def candidate_json(**overrides):
    data = {
        "status": "matched",
        "command_type": "review_pending",
        "target_question_number": None,
        "answer_text": None,
        "reason": "用户希望查看待确认问题。",
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


class LLMIntentClassifierTests(unittest.TestCase):
    def request(self):
        return IntentClassificationInput(
            raw_text="我想看看还有什么没回答。",
            session_active=True,
            pending_question_numbers=(1, 2),
            current_question_number=2,
        )

    def test_sends_prompts_and_returns_strict_matched_candidate(self):
        client = FakeLLMClient(candidate_json())
        classifier = LLMIntentClassifier(client)

        candidate = classifier.classify(self.request())

        self.assertEqual(
            candidate.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(candidate.status, IntentCandidateStatus.MATCHED)
        self.assertEqual(len(client.calls), 1)
        self.assertIn("意图分类器", client.calls[0]["system_prompt"])
        self.assertIn(
            "我想看看还有什么没回答",
            client.calls[0]["user_prompt"],
        )
        self.assertIn(
            '"current_question_number": 2',
            client.calls[0]["user_prompt"],
        )

    def test_exposes_generation_attempts_and_processing_seconds(self):
        client = FakeLLMClient(candidate_json())

        result = LLMIntentClassifier(client).classify_with_metrics(
            self.request()
        )

        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.processing_seconds, 0.1)
        self.assertEqual(
            result.candidate.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )

    def test_accepts_clean_uncertain_candidate(self):
        client = FakeLLMClient(candidate_json(
            status="uncertain",
            command_type=None,
            reason="语义不足。",
        ))

        candidate = LLMIntentClassifier(client).classify(self.request())

        self.assertEqual(candidate.status, IntentCandidateStatus.UNCERTAIN)
        self.assertIsNone(candidate.command_type)

    def test_rejects_invalid_json_or_non_object(self):
        for content, expected in (
            ("not-json", "不是合法JSON"),
            ("[]", "顶层必须是JSON对象"),
        ):
            with self.subTest(content=content):
                classifier = LLMIntentClassifier(FakeLLMClient(content))
                with self.assertRaisesRegex(
                    IntentClassifierError,
                    expected,
                ):
                    classifier.classify(self.request())

    def test_reuses_candidate_schema_validation(self):
        classifier = LLMIntentClassifier(FakeLLMClient(candidate_json(
            execute_now=True,
        )))

        with self.assertRaisesRegex(IntentClassifierError, "额外字段"):
            classifier.classify(self.request())

    def test_propagates_client_error_for_router_to_degrade(self):
        error = LLMClientError(
            "timeout",
            attempts=2,
            processing_seconds=1.5,
        )
        classifier = LLMIntentClassifier(FakeLLMClient(error=error))

        with self.assertRaises(LLMClientError) as caught:
            classifier.classify(self.request())

        self.assertIs(caught.exception, error)
        self.assertEqual(caught.exception.attempts, 2)


if __name__ == "__main__":
    unittest.main()
