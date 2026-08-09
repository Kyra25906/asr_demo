import unittest

from src.core.intent_policy import (
    INTENT_POLICIES,
    IntentDisposition,
    IntentEvidence,
    IntentPolicyEvaluator,
    IntentRisk,
)
from src.core.interaction_command import InteractionCommandType


class IntentPolicyTests(unittest.TestCase):
    def test_every_command_type_has_exactly_one_policy(self):
        self.assertEqual(
            set(INTENT_POLICIES),
            set(InteractionCommandType),
        )

    def test_normal_text_always_returns_to_experiment_pipeline(self):
        for evidence in IntentEvidence:
            with self.subTest(evidence=evidence):
                decision = IntentPolicyEvaluator.evaluate(
                    InteractionCommandType.NORMAL,
                    evidence,
                )
                self.assertEqual(
                    decision.disposition,
                    IntentDisposition.PASS_TO_EXPERIMENT,
                )
                self.assertFalse(decision.may_execute_now)

    def test_exact_end_command_can_execute(self):
        decision = IntentPolicyEvaluator.evaluate(
            InteractionCommandType.END_SESSION,
            IntentEvidence.EXACT_RULE,
        )

        self.assertEqual(decision.risk, IntentRisk.HIGH)
        self.assertEqual(
            decision.disposition,
            IntentDisposition.EXECUTE,
        )
        self.assertTrue(decision.may_execute_now)

    def test_semantic_or_llm_end_candidate_never_executes_directly(self):
        for evidence in (
            IntentEvidence.LOCAL_SEMANTIC,
            IntentEvidence.LLM_CANDIDATE,
        ):
            with self.subTest(evidence=evidence):
                decision = IntentPolicyEvaluator.evaluate(
                    InteractionCommandType.END_SESSION,
                    evidence,
                )
                self.assertEqual(
                    decision.disposition,
                    IntentDisposition.REQUEST_CONFIRMATION,
                )
                self.assertFalse(decision.may_execute_now)

    def test_low_risk_review_allows_semantic_candidate_with_context(self):
        decision = IntentPolicyEvaluator.evaluate(
            InteractionCommandType.REVIEW_PENDING,
            IntentEvidence.LOCAL_SEMANTIC,
        )

        self.assertEqual(decision.risk, IntentRisk.LOW)
        self.assertEqual(
            decision.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )
        self.assertTrue(decision.may_execute_now)

    def test_reversible_defer_allows_only_local_semantic_candidate(self):
        local = IntentPolicyEvaluator.evaluate(
            InteractionCommandType.DEFER_CURRENT,
            IntentEvidence.LOCAL_SEMANTIC,
        )
        llm = IntentPolicyEvaluator.evaluate(
            InteractionCommandType.DEFER_CURRENT,
            IntentEvidence.LLM_CANDIDATE,
        )

        self.assertEqual(
            local.disposition,
            IntentDisposition.REQUIRE_CONTEXT,
        )
        self.assertEqual(
            llm.disposition,
            IntentDisposition.DO_NOT_EXECUTE,
        )

    def test_llm_cannot_directly_write_confirmation_state(self):
        for command_type in (
            InteractionCommandType.AFFIRM,
            InteractionCommandType.DENY,
            InteractionCommandType.TARGETED_ANSWER,
        ):
            with self.subTest(command_type=command_type):
                decision = IntentPolicyEvaluator.evaluate(
                    command_type,
                    IntentEvidence.LLM_CANDIDATE,
                )
                self.assertEqual(
                    decision.disposition,
                    IntentDisposition.DO_NOT_EXECUTE,
                )
                self.assertFalse(decision.may_execute_now)


if __name__ == "__main__":
    unittest.main()
