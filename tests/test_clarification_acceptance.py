import unittest
from dataclasses import FrozenInstanceError

from src.asr.schemas import ASRResult
from src.core.clarification_acceptance import (
    ClarificationActionPlanner,
    ClarificationActionType,
    ClarificationContextSnapshot,
    ClarificationMutationPermission,
)
from src.core.experiment_acceptance import ExperimentCandidateAcceptor
from src.core.interaction_command import InteractionCommandType
from src.core.intent_policy import IntentEvidence, IntentPolicyEvaluator
from src.core.pending_clarification import PendingClarification
from src.core.unified_dispatch import UnifiedDispatchPlanner
from src.core.unified_dispatch_execution import DispatchExecutionRequest
from src.core.unified_understanding import (
    ExperimentUnderstanding,
    UnifiedUnderstandingResult,
    build_degraded_understanding,
)
from src.llm.processor import ProcessOutcome
from src.llm.schemas import ExperimentEvent, ExperimentEventType, LLMAnalysisResult
from src.llm.unified_router import UnifiedRouteResult
from tests.test_experiment_acceptance import request_for
from tests.test_unified_dispatch import control_route, exact_route


TEXT = "用户忠实转写。"


def pending(
    clarification_id="clarification-1",
    number=1,
    *,
    requires_confirmation=True,
):
    return PendingClarification(
        clarification_id=clarification_id,
        display_number=number,
        source_segment_id=1,
        source_raw_text="加入缓冲液。",
        question="是否使用移液枪？",
        missing_fields=() if requires_confirmation else ("duration",),
        requires_confirmation=requires_confirmation,
    )


def dispatch_request(route, *, text=TEXT):
    return DispatchExecutionRequest(
        request_id="request-control",
        session_id="session-1",
        segment_id=2,
        asr_evidence=ASRResult(
            asr_transcript=text,
            asr_model_raw_text=f"<|zh|>{text}",
            audio_path="fixed://control.wav",
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fake-asr",
            language="zh",
        ),
        plan=UnifiedDispatchPlanner.plan(route),
    )


class ClarificationAcceptanceTests(unittest.TestCase):
    def test_exact_review_forms_read_only_action(self):
        request = dispatch_request(exact_route(
            InteractionCommandType.REVIEW_PENDING,
            raw_text=TEXT,
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot((pending(),)),
        )
        self.assertEqual(action.action_type, ClarificationActionType.REVIEW)
        self.assertEqual(
            action.mutation_permission,
            ClarificationMutationPermission.READ_ONLY,
        )
        self.assertTrue(action.requires_evidence_persistence)

    def test_llm_low_risk_review_can_only_form_read_only_action(self):
        request = dispatch_request(control_route(
            InteractionCommandType.REVIEW_PENDING
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot((pending(),)),
        )
        self.assertEqual(action.action_type, ClarificationActionType.REVIEW)
        self.assertIsNone(action.target_clarification_id)

    def test_exact_defer_targets_current_revision_without_mutating_it(self):
        item = pending()
        request = dispatch_request(exact_route(
            InteractionCommandType.DEFER_CURRENT,
            raw_text=TEXT,
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot(
                (item,),
                current_clarification_id=item.clarification_id,
            ),
        )
        self.assertEqual(action.action_type, ClarificationActionType.DEFER)
        self.assertEqual(action.target_clarification_id, item.clarification_id)
        self.assertEqual(action.expected_revision, item.revision)
        self.assertTrue(item.is_active)

    def test_defer_without_current_question_becomes_no_action(self):
        request = dispatch_request(exact_route(
            InteractionCommandType.DEFER_CURRENT,
            raw_text=TEXT,
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot((pending(),)),
        )
        self.assertEqual(action.action_type, ClarificationActionType.NO_ACTION)

    def test_exact_affirm_and_deny_prepare_targeted_updates(self):
        item = pending()
        context = ClarificationContextSnapshot(
            (item,),
            current_clarification_id=item.clarification_id,
        )
        for command_type, expected in (
            (InteractionCommandType.AFFIRM, ClarificationActionType.CONFIRM),
            (
                InteractionCommandType.DENY,
                ClarificationActionType.REJECT_SUGGESTION,
            ),
        ):
            with self.subTest(command_type=command_type):
                request = dispatch_request(exact_route(
                    command_type,
                    raw_text="是" if command_type == InteractionCommandType.AFFIRM else "不是",
                ), text="是" if command_type == InteractionCommandType.AFFIRM else "不是")
                action = ClarificationActionPlanner.from_dispatch(
                    request,
                    context,
                )
                self.assertEqual(action.action_type, expected)
                self.assertEqual(action.target_display_number, 1)
                self.assertTrue(action.requires_evidence_persistence)

    def test_exact_targeted_answer_requires_existing_number_and_answer(self):
        # 使用真实解析器生成包含编号和答案的完整命令。
        from src.core.interaction_command import InteractionCommandParser
        command = InteractionCommandParser.parse("问题2五分钟")
        route = UnifiedRouteResult(
            exact_command=command,
            decision=IntentPolicyEvaluator.evaluate(
                InteractionCommandType.TARGETED_ANSWER,
                IntentEvidence.EXACT_RULE,
            ),
        )
        request = dispatch_request(route, text="问题2五分钟")
        item = pending("clarification-2", 2, requires_confirmation=False)
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot((item,)),
        )
        self.assertEqual(action.action_type, ClarificationActionType.ANSWER)
        self.assertEqual(action.answer_text, "五分钟")
        self.assertEqual(action.target_clarification_id, "clarification-2")

    def test_targeted_answer_missing_target_or_answer_becomes_no_action(self):
        from src.core.interaction_command import InteractionCommandParser

        for text, context in (
            ("问题9五分钟", ClarificationContextSnapshot((pending(),))),
            (
                "问题2",
                ClarificationContextSnapshot((pending("clarification-2", 2),)),
            ),
        ):
            with self.subTest(text=text):
                command = InteractionCommandParser.parse(text)
                route = UnifiedRouteResult(
                    exact_command=command,
                    decision=IntentPolicyEvaluator.evaluate(
                        InteractionCommandType.TARGETED_ANSWER,
                        IntentEvidence.EXACT_RULE,
                    ),
                )
                action = ClarificationActionPlanner.from_dispatch(
                    dispatch_request(route, text=text),
                    context,
                )
                self.assertEqual(
                    action.action_type,
                    ClarificationActionType.NO_ACTION,
                )

    def test_llm_medium_risk_answer_stays_no_action_even_with_valid_number(self):
        request = dispatch_request(control_route(
            InteractionCommandType.TARGETED_ANSWER,
            target_question_number=2,
            answer_text="五分钟",
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot((pending("clarification-2", 2),)),
        )
        self.assertEqual(action.action_type, ClarificationActionType.NO_ACTION)
        self.assertEqual(action.mutation_permission, ClarificationMutationPermission.NONE)
        self.assertIsNone(action.target_clarification_id)

    def test_all_llm_medium_risk_state_candidates_stay_no_action(self):
        cases = (
            (InteractionCommandType.DEFER_CURRENT, {}),
            (InteractionCommandType.AFFIRM, {"answer_text": "是"}),
            (InteractionCommandType.DENY, {"answer_text": "不是"}),
            (
                InteractionCommandType.TARGETED_ANSWER,
                {"target_question_number": 1, "answer_text": "五分钟"},
            ),
        )
        item = pending()
        context = ClarificationContextSnapshot(
            (item,),
            current_clarification_id=item.clarification_id,
        )
        for command_type, fields in cases:
            with self.subTest(command_type=command_type):
                request = dispatch_request(control_route(command_type, **fields))
                action = ClarificationActionPlanner.from_dispatch(
                    request,
                    context,
                )
                self.assertEqual(
                    action.action_type,
                    ClarificationActionType.NO_ACTION,
                )
                self.assertIsNone(action.target_clarification_id)

    def test_follow_up_from_accepted_experiment_forms_create_plan(self):
        analysis = LLMAnalysisResult(
            events=[ExperimentEvent(
                event_type=ExperimentEventType.OPERATION,
                raw_text="加入缓冲液。",
                normalized_text="加入缓冲液。",
                missing_fields=["amount_value", "amount_unit"],
                source_session_id="session-1",
                source_segment_id=1,
            )],
            should_ask_follow_up=True,
            follow_up_question="加入多少缓冲液？",
        )
        accepted = ExperimentCandidateAcceptor.accept(request_for(
            UnifiedUnderstandingResult(
                raw_text="加入缓冲液。",
                experiment=ExperimentUnderstanding(analysis),
            )
        ))
        action = ClarificationActionPlanner.from_experiment(accepted)
        self.assertEqual(action.action_type, ClarificationActionType.CREATE)
        self.assertEqual(action.missing_fields, ("amount_value", "amount_unit"))
        self.assertEqual(action.question, "加入多少缓冲液？")
        self.assertTrue(action.requires_evidence_persistence)

    def test_degraded_note_does_not_create_false_question(self):
        degraded = build_degraded_understanding(
            raw_text="加入五毫升缓冲液。",
            session_id="session-1",
            segment_id=1,
            reason="timeout",
        )
        accepted = ExperimentCandidateAcceptor.accept(request_for(
            degraded,
            degraded=True,
            error="TimeoutError: timeout",
        ))
        action = ClarificationActionPlanner.from_experiment(accepted)
        self.assertEqual(action.action_type, ClarificationActionType.NO_ACTION)

    def test_context_snapshot_rejects_duplicate_or_non_active_current(self):
        with self.assertRaisesRegex(ValueError, "display_number"):
            ClarificationContextSnapshot((pending("a", 1), pending("b", 1)))

    def test_action_is_immutable_and_has_no_commit_method(self):
        request = dispatch_request(exact_route(
            InteractionCommandType.REVIEW_PENDING,
            raw_text=TEXT,
        ))
        action = ClarificationActionPlanner.from_dispatch(
            request,
            ClarificationContextSnapshot(),
        )
        with self.assertRaises(FrozenInstanceError):
            action.reason = "改写"
        self.assertFalse(hasattr(action, "commit"))


if __name__ == "__main__":
    unittest.main()
