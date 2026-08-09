import unittest

from src.core.intent_classifier import (
    FakeIntentClassifier,
    IntentCandidate,
    IntentCandidateStatus,
    IntentClassificationInput,
    IntentClassifierError,
)
from src.core.intent_policy import IntentEvidence
from src.core.interaction_command import InteractionCommandType


class IntentClassificationInputTests(unittest.TestCase):
    def test_accepts_minimal_context(self):
        request = IntentClassificationInput(
            raw_text="我想看看还有什么没回答。",
            session_active=True,
            pending_question_numbers=(1, 3),
            current_question_number=3,
        )

        self.assertEqual(request.pending_question_numbers, (1, 3))

    def test_rejects_empty_text_or_invalid_question_context(self):
        with self.assertRaisesRegex(ValueError, "不能为空"):
            IntentClassificationInput("  ", True)
        with self.assertRaisesRegex(ValueError, "不能重复"):
            IntentClassificationInput("是的", True, (1, 1))
        with self.assertRaisesRegex(ValueError, "必须存在"):
            IntentClassificationInput("是的", True, (1,), 2)


class IntentCandidateTests(unittest.TestCase):
    def test_strictly_parses_valid_llm_candidate(self):
        candidate = IntentCandidate.from_mapping({
            "status": "matched",
            "command_type": "review_pending",
            "target_question_number": None,
            "answer_text": None,
            "reason": "用户希望查看尚未解决的问题。",
        })

        self.assertEqual(
            candidate.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(candidate.evidence, IntentEvidence.LLM_CANDIDATE)

    def test_rejects_missing_extra_or_unknown_fields(self):
        valid = {
            "status": "matched",
            "command_type": "normal",
            "target_question_number": None,
            "answer_text": None,
            "reason": None,
        }
        for changed, message in (
            ({key: value for key, value in valid.items() if key != "reason"}, "缺少"),
            ({**valid, "execute_now": True}, "额外"),
            ({**valid, "command_type": "delete_all"}, "不受支持"),
        ):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(IntentClassifierError, message):
                    IntentCandidate.from_mapping(changed)

    def test_targeted_answer_requires_positive_target_number(self):
        with self.assertRaisesRegex(IntentClassifierError, "必须包含"):
            IntentCandidate.from_mapping({
                "status": "matched",
                "command_type": "targeted_answer",
                "target_question_number": None,
                "answer_text": "离心5分钟",
                "reason": None,
            })

    def test_non_targeted_intent_cannot_smuggle_target_number(self):
        with self.assertRaisesRegex(IntentClassifierError, "只有指定"):
            IntentCandidate.from_mapping({
                "status": "matched",
                "command_type": "end_session",
                "target_question_number": 1,
                "answer_text": None,
                "reason": "结束",
            })

    def test_non_answer_intent_cannot_smuggle_answer_text(self):
        with self.assertRaisesRegex(IntentClassifierError, "只有确认"):
            IntentCandidate.from_mapping({
                "status": "matched",
                "command_type": "end_session",
                "target_question_number": None,
                "answer_text": "立即执行",
                "reason": "结束",
            })

    def test_candidate_cannot_claim_exact_rule_evidence(self):
        with self.assertRaisesRegex(ValueError, "LLM候选"):
            IntentCandidate(
                command_type=InteractionCommandType.END_SESSION,
                evidence=IntentEvidence.EXACT_RULE,
            )

    def test_uncertain_candidate_must_abstain_cleanly(self):
        candidate = IntentCandidate.from_mapping({
            "status": "uncertain",
            "command_type": None,
            "target_question_number": None,
            "answer_text": None,
            "reason": "语义不足。",
        })

        self.assertEqual(candidate.status, IntentCandidateStatus.UNCERTAIN)
        self.assertIsNone(candidate.command_type)

        with self.assertRaisesRegex(IntentClassifierError, "必须为null"):
            IntentCandidate.from_mapping({
                "status": "uncertain",
                "command_type": "end_session",
                "target_question_number": None,
                "answer_text": None,
                "reason": "不确定。",
            })


class FakeIntentClassifierTests(unittest.TestCase):
    def test_returns_configured_candidate_and_records_request(self):
        candidate = IntentCandidate(
            command_type=InteractionCommandType.REVIEW_PENDING,
        )
        classifier = FakeIntentClassifier({"还有什么问题": candidate})
        request = IntentClassificationInput(
            raw_text="还有什么问题",
            session_active=True,
        )

        self.assertIs(classifier.classify(request), candidate)
        self.assertEqual(classifier.requests, [request])

    def test_can_simulate_external_failure(self):
        classifier = FakeIntentClassifier(error=TimeoutError("timeout"))

        with self.assertRaises(TimeoutError):
            classifier.classify(
                IntentClassificationInput("看看问题", True)
            )


if __name__ == "__main__":
    unittest.main()
