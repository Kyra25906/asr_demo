import unittest

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


if __name__ == "__main__":
    unittest.main()
