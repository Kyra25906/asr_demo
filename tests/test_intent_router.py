import unittest

from src.core.intent_classifier import (
    FakeIntentClassifier,
    IntentCandidate,
    IntentCandidateStatus,
)
from src.core.intent_policy import (
    IntentDisposition,
    IntentEvidence,
)
from src.core.intent_router import (
    IntentRouteResult,
    IntentRouter,
)
from src.core.interaction_command import (
    InteractionCommand,
    InteractionCommandType,
)


class IntentRouterTests(unittest.TestCase):
    def setUp(self):
        self.router = IntentRouter()

    def test_routes_normal_experiment_text_to_experiment_pipeline(self):
        result = self.router.route("加入5毫升缓冲液。")

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.NORMAL,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.PASS_TO_EXPERIMENT,
        )
        self.assertTrue(result.is_experiment_text)

    def test_routes_review_command_to_context_handler(self):
        result = self.router.route("查看待确认问题。")

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )
        self.assertFalse(result.is_experiment_text)

    def test_routes_exact_end_command_to_execution(self):
        result = self.router.route("结束实验记录。")

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.END_SESSION,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.EXECUTE,
        )
        self.assertEqual(
            result.decision.evidence,
            IntentEvidence.EXACT_RULE,
        )

    def test_preserves_target_number_and_answer(self):
        result = self.router.route("问题2，离心5分钟。")

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.TARGETED_ANSWER,
        )
        self.assertEqual(result.command.target_question_number, 2)
        self.assertEqual(result.command.answer_text, "离心5分钟")
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )

    def test_preserves_raw_asr_text(self):
        raw_text = "  查看 待确认问题。😔 "
        result = self.router.route(raw_text)

        self.assertEqual(result.raw_text, raw_text)
        self.assertEqual(result.command.raw_text, raw_text)

    def test_natural_expression_is_not_guessed_in_exact_router(self):
        result = self.router.route("我想看看还有什么没回答。")

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.NORMAL,
        )
        self.assertTrue(result.is_experiment_text)


class IntentRouteResultValidationTests(unittest.TestCase):
    def test_rejects_mismatched_command_and_decision(self):
        router = IntentRouter()
        end_decision = router.route("结束实验记录").decision
        normal_command = InteractionCommand(
            command_type=InteractionCommandType.NORMAL,
            raw_text="记录温度",
            normalized_text="记录温度",
        )

        with self.assertRaisesRegex(ValueError, "必须一致"):
            IntentRouteResult(
                command=normal_command,
                decision=end_decision,
            )


class IntentRouterClassifierIntegrationTests(unittest.TestCase):
    def test_exact_command_bypasses_classifier(self):
        classifier = FakeIntentClassifier(error=AssertionError("不应调用"))
        router = IntentRouter(classifier=classifier)

        result = router.route("结束实验记录。")

        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.EXECUTE,
        )
        self.assertFalse(result.classifier_used)
        self.assertEqual(classifier.requests, [])

    def test_llm_review_candidate_passes_through_risk_policy(self):
        candidate = IntentCandidate(
            command_type=InteractionCommandType.REVIEW_PENDING,
            reason="用户想查看尚未回答的问题。",
        )
        classifier = FakeIntentClassifier({
            "我想看看还有什么没回答。": candidate,
        })
        router = IntentRouter(classifier=classifier)

        result = router.route(
            "我想看看还有什么没回答。",
            pending_question_numbers=(1, 2),
            current_question_number=2,
        )

        self.assertEqual(
            result.command.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )
        self.assertEqual(
            result.decision.evidence,
            IntentEvidence.LLM_CANDIDATE,
        )
        self.assertTrue(result.classifier_used)
        self.assertEqual(result.candidate_reason, candidate.reason)
        self.assertEqual(
            classifier.requests[0].pending_question_numbers,
            (1, 2),
        )

    def test_llm_end_candidate_requires_confirmation(self):
        router = IntentRouter(classifier=FakeIntentClassifier({
            "今天先记到这里吧。": IntentCandidate(
                command_type=InteractionCommandType.END_SESSION,
            ),
        }))

        result = router.route("今天先记到这里吧。")

        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUEST_CONFIRMATION,
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_llm_targeted_answer_preserves_target_and_answer(self):
        router = IntentRouter(classifier=FakeIntentClassifier({
            "关于第二个，是五分钟。": IntentCandidate(
                command_type=InteractionCommandType.TARGETED_ANSWER,
                target_question_number=2,
                answer_text="五分钟",
            ),
        }))

        result = router.route(
            "关于第二个，是五分钟。",
            pending_question_numbers=(1, 2),
        )

        self.assertEqual(result.command.target_question_number, 2)
        self.assertEqual(result.command.answer_text, "五分钟")
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.DO_NOT_EXECUTE,
        )

    def test_llm_normal_candidate_continues_as_experiment_text(self):
        router = IntentRouter(classifier=FakeIntentClassifier())

        result = router.route("加入五毫升缓冲液。")

        self.assertTrue(result.classifier_used)
        self.assertTrue(result.is_experiment_text)
        self.assertIsNone(result.classification_error)

    def test_classifier_timeout_degrades_without_control_action(self):
        router = IntentRouter(classifier=FakeIntentClassifier(
            error=TimeoutError("timeout"),
        ))
        raw_text = "我想看看还有什么没回答。"

        result = router.route(raw_text)

        self.assertEqual(result.raw_text, raw_text)
        self.assertTrue(result.is_experiment_text)
        self.assertTrue(result.classifier_used)
        self.assertEqual(
            result.classification_error,
            "TimeoutError: timeout",
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_uncertain_candidate_abstains_without_control_action(self):
        router = IntentRouter(classifier=FakeIntentClassifier({
            "这个差不多了。": IntentCandidate(
                status=IntentCandidateStatus.UNCERTAIN,
                reason="可能描述操作，也可能表示结束。",
            ),
        }))

        result = router.route("这个差不多了。")

        self.assertTrue(result.classifier_used)
        self.assertTrue(result.classification_uncertain)
        self.assertTrue(result.is_experiment_text)
        self.assertIsNone(result.classification_error)
        self.assertFalse(result.decision.may_execute_now)


if __name__ == "__main__":
    unittest.main()
