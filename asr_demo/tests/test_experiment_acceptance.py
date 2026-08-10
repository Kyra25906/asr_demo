import unittest
from dataclasses import FrozenInstanceError, replace

from src.asr.schemas import ASRResult
from src.core.experiment_acceptance import (
    ExperimentAcceptanceKind,
    ExperimentCandidateAcceptor,
)
from src.core.intent_policy import IntentEvidence, IntentPolicyEvaluator
from src.core.interaction_command import InteractionCommandType
from src.core.unified_dispatch import UnifiedDispatchPlanner
from src.core.unified_dispatch_execution import DispatchExecutionRequest
from src.core.unified_understanding import (
    ExperimentUnderstanding,
    UnifiedUnderstandingResult,
    build_degraded_understanding,
)
from src.llm.processor import ProcessOutcome
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.llm.unified_router import UnifiedRouteResult
from tests.test_unified_dispatch import exact_route


TRANSCRIPT = "加入五毫升缓冲液。"


def evidence(transcript=TRANSCRIPT):
    return ASRResult(
        asr_transcript=transcript,
        asr_model_raw_text=f"<|zh|>{transcript}",
        audio_path="fixed://experiment.wav",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )


def normal_analysis(
    *,
    transcript=TRANSCRIPT,
    session_id="session-1",
    segment_id=1,
):
    return LLMAnalysisResult(events=[ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=transcript,
        normalized_text="加入5毫升缓冲液。",
        entities=ExperimentEntities(
            action="加入",
            object="缓冲液",
            amount_value="5",
            amount_unit="毫升",
        ),
        source_session_id=session_id,
        source_segment_id=segment_id,
    )])


def request_for(understanding, *, degraded=False, error=None):
    outcome = ProcessOutcome(
        value=understanding,
        degraded=degraded,
        error=error,
        llm_attempts=2 if degraded else 1,
        llm_processing_seconds=0.3 if degraded else 0.2,
    )
    route = UnifiedRouteResult(
        understanding_outcome=outcome,
        decision=IntentPolicyEvaluator.evaluate(
            InteractionCommandType.NORMAL,
            IntentEvidence.LLM_CANDIDATE,
        ),
    )
    return DispatchExecutionRequest(
        request_id="request-1",
        session_id="session-1",
        segment_id=1,
        asr_evidence=evidence(understanding.raw_text),
        plan=UnifiedDispatchPlanner.plan(route),
    )


def normal_request():
    return request_for(UnifiedUnderstandingResult(
        raw_text=TRANSCRIPT,
        experiment=ExperimentUnderstanding(normal_analysis()),
    ))


class ExperimentAcceptanceTests(unittest.TestCase):
    def test_accepts_normal_experiment_with_identity_and_metrics(self):
        accepted = ExperimentCandidateAcceptor.accept(normal_request())
        self.assertEqual(
            accepted.kind,
            ExperimentAcceptanceKind.STRUCTURED_EXPERIMENT,
        )
        self.assertEqual(accepted.event_count, 1)
        self.assertFalse(accepted.degraded)
        self.assertEqual(accepted.llm_attempts, 1)

    def test_snapshot_is_immutable_and_materializes_fresh_analysis(self):
        accepted = ExperimentCandidateAcceptor.accept(normal_request())
        with self.assertRaises(FrozenInstanceError):
            accepted.event_count = 2
        first = accepted.materialize_analysis()
        first.events.clear()
        second = accepted.materialize_analysis()
        self.assertEqual(len(second.events), 1)

    def test_legacy_outcome_adapter_does_not_call_llm(self):
        accepted = ExperimentCandidateAcceptor.accept(normal_request())
        outcome = accepted.to_process_outcome()
        self.assertFalse(outcome.degraded)
        self.assertEqual(outcome.value.events[0].raw_text, TRANSCRIPT)
        self.assertEqual(outcome.llm_processing_seconds, 0.2)

    def test_rejects_wrong_event_transcript(self):
        understanding = UnifiedUnderstandingResult(
            raw_text=TRANSCRIPT,
            experiment=ExperimentUnderstanding(normal_analysis(
                transcript="被改写的原文。",
            )),
        )
        with self.assertRaisesRegex(ValueError, "原文"):
            ExperimentCandidateAcceptor.accept(request_for(understanding))

    def test_rejects_wrong_event_session_or_segment_source(self):
        for analysis, expected in (
            (normal_analysis(session_id="other"), "session"),
            (normal_analysis(segment_id=2), "segment"),
        ):
            with self.subTest(expected=expected):
                understanding = UnifiedUnderstandingResult(
                    raw_text=TRANSCRIPT,
                    experiment=ExperimentUnderstanding(analysis),
                )
                with self.assertRaisesRegex(ValueError, expected):
                    ExperimentCandidateAcceptor.accept(
                        request_for(understanding)
                    )

    def test_rejects_empty_experiment_candidate(self):
        understanding = UnifiedUnderstandingResult(
            raw_text=TRANSCRIPT,
            experiment=ExperimentUnderstanding(LLMAnalysisResult()),
        )
        with self.assertRaisesRegex(ValueError, "至少需要一个事件"):
            ExperimentCandidateAcceptor.accept(request_for(understanding))

    def test_acceptance_rechecks_missing_fields_follow_up_conflict(self):
        analysis = normal_analysis()
        analysis.events[0].missing_fields = ["temperature", "duration"]
        understanding = UnifiedUnderstandingResult(
            raw_text=TRANSCRIPT,
            experiment=ExperimentUnderstanding(analysis),
        )
        with self.assertRaisesRegex(ValueError, "追问标志"):
            ExperimentCandidateAcceptor.accept(request_for(understanding))

    def test_acceptance_rechecks_spurious_follow_up(self):
        analysis = normal_analysis()
        analysis.should_ask_follow_up = True
        analysis.follow_up_question = "请补充信息。"
        understanding = UnifiedUnderstandingResult(
            raw_text=TRANSCRIPT,
            experiment=ExperimentUnderstanding(analysis),
        )
        with self.assertRaisesRegex(ValueError, "追问标志"):
            ExperimentCandidateAcceptor.accept(request_for(understanding))

    def test_context_dispatch_cannot_enter_experiment_acceptor(self):
        plan = UnifiedDispatchPlanner.plan(exact_route(
            InteractionCommandType.REVIEW_PENDING,
            raw_text=TRANSCRIPT,
        ))
        request = DispatchExecutionRequest(
            request_id="request-context",
            session_id="session-1",
            segment_id=1,
            asr_evidence=evidence(),
            plan=plan,
        )
        with self.assertRaisesRegex(ValueError, "统一理解结果"):
            ExperimentCandidateAcceptor.accept(request)

    def test_accepts_degraded_result_only_as_faithful_note(self):
        degraded = build_degraded_understanding(
            raw_text=TRANSCRIPT,
            session_id="session-1",
            segment_id=1,
            reason="timeout",
        )
        accepted = ExperimentCandidateAcceptor.accept(request_for(
            degraded,
            degraded=True,
            error="TimeoutError: timeout",
        ))
        self.assertEqual(
            accepted.kind,
            ExperimentAcceptanceKind.DEGRADED_EVIDENCE_NOTE,
        )
        event = accepted.materialize_analysis().events[0]
        self.assertEqual(event.event_type, ExperimentEventType.NOTE)
        self.assertEqual(event.normalized_text, TRANSCRIPT)

    def test_degraded_shape_cannot_enter_normal_experiment_dispatch(self):
        degraded = build_degraded_understanding(
            raw_text=TRANSCRIPT,
            session_id="session-1",
            segment_id=1,
            reason="timeout",
        )
        request = request_for(
            degraded,
            degraded=True,
            error="TimeoutError: timeout",
        )
        forged_outcome = replace(
            request.plan.route_result.understanding_outcome,
            degraded=False,
            error=None,
        )
        forged_route = replace(
            request.plan.route_result,
            understanding_outcome=forged_outcome,
        )
        forged_request = replace(
            request,
            plan=UnifiedDispatchPlanner.plan(forged_route),
        )
        with self.assertRaisesRegex(ValueError, "不能伪装"):
            ExperimentCandidateAcceptor.accept(forged_request)

    def test_degraded_note_rejects_normalized_rewrite(self):
        degraded = build_degraded_understanding(
            raw_text=TRANSCRIPT,
            session_id="session-1",
            segment_id=1,
            reason="timeout",
        )
        degraded.experiment.analysis.events[0].normalized_text = "移液枪。"
        with self.assertRaisesRegex(ValueError, "不能改写"):
            ExperimentCandidateAcceptor.accept(request_for(
                degraded,
                degraded=True,
                error="TimeoutError: timeout",
            ))


if __name__ == "__main__":
    unittest.main()
