import unittest

from src.asr.schemas import ASRResult
from src.core.reply_coordinator import ReplyCoordinator
from src.core.unified_observer import (
    UnifiedObservation,
    UnifiedObservationStatus,
    UnifiedObserver,
)


class FakeBypass:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.inputs = []

    def inspect(self, value):
        self.inputs.append(value)
        if self.error:
            raise self.error
        return self.result


class Value:
    def __init__(self, value):
        self.value = value


class Accepted:
    kind = Value("structured_experiment")

    @staticmethod
    def materialize_analysis():
        event = type("Event", (), {"missing_fields": ["temperature"]})()
        return type("Analysis", (), {
            "events": [event],
            "should_ask_follow_up": True,
        })()


class Action:
    action_type = Value("create")


class Plan:
    destination = Value("experiment_pipeline")
    permission = Value("forward_experiment_analysis")


class Request:
    plan = Plan()


class Result:
    execution_request = Request()
    accepted_experiment = Accepted()
    clarification_action = Action()
    end_confirmation_requested = False


def asr(text="加入缓冲液。"):
    return ASRResult(
        asr_transcript=text,
        asr_model_raw_text=f"raw:{text}",
        audio_path="fixed://chain.wav",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )


class UnifiedObserverTests(unittest.TestCase):
    def test_success_returns_redacted_summary_and_preserves_input(self):
        bypass = FakeBypass(result=Result())
        observation = UnifiedObserver(bypass).observe(
            request_id="unified-session-1-segment-2",
            session_id="session-1",
            segment_id=2,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
        )
        self.assertEqual(observation.status, UnifiedObservationStatus.OBSERVED)
        self.assertEqual(observation.destination, "experiment_pipeline")
        self.assertEqual(observation.clarification_action, "create")
        self.assertEqual(observation.missing_fields, ("temperature",))
        self.assertTrue(observation.follow_up_required)
        self.assertEqual(bypass.inputs[0].asr_result.asr_transcript, "加入缓冲液。")
        self.assertFalse(hasattr(observation, "raw_text"))

    def test_failure_is_isolated_without_secret_error_detail(self):
        observation = UnifiedObserver(
            FakeBypass(error=RuntimeError("secret transcript"))
        ).observe(
            request_id="unified-session-1-segment-2",
            session_id="session-1",
            segment_id=2,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
        )
        self.assertEqual(observation.status, UnifiedObservationStatus.FAILED)
        self.assertEqual(observation.error_type, "RuntimeError")
        self.assertNotIn("secret", repr(observation))

    def test_snapshot_reads_context_without_mutating_coordinator(self):
        coordinator = ReplyCoordinator()
        before = coordinator.active_clarifications()
        bypass = FakeBypass(result=Result())
        UnifiedObserver(bypass).observe(
            request_id="unified-session-1-segment-3",
            session_id="session-1",
            segment_id=3,
            asr_result=asr(),
            reply_coordinator=coordinator,
        )
        self.assertEqual(coordinator.active_clarifications(), before)
        self.assertEqual(bypass.inputs[0].clarification_context.unresolved, before)

    def test_observe_returns_pending_action_without_executing(self):
        coordinator = ReplyCoordinator()
        before = coordinator.active_clarifications()
        bypass = FakeBypass(result=Result())
        observation = UnifiedObserver(bypass).observe(
            request_id="unified-session-1-segment-4",
            session_id="session-1",
            segment_id=4,
            asr_result=asr(),
            reply_coordinator=coordinator,
        )
        self.assertIsNotNone(observation.pending_action)
        self.assertEqual(observation.pending_action.action_type.value, "create")
        self.assertFalse(observation.executed)
        self.assertEqual(coordinator.active_clarifications(), before)

    def test_observe_forwards_recent_context_to_bypass_input(self):
        bypass = FakeBypass(result=Result())
        UnifiedObserver(bypass).observe(
            request_id="unified-session-1-segment-5",
            session_id="session-1",
            segment_id=5,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
            recent_context=("[operation] 加入缓冲液。",),
        )
        self.assertEqual(
            bypass.inputs[0].recent_context,
            ("[operation] 加入缓冲液。",),
        )

    def test_observe_recent_context_defaults_to_empty_tuple(self):
        bypass = FakeBypass(result=Result())
        UnifiedObserver(bypass).observe(
            request_id="unified-session-1-segment-6",
            session_id="session-1",
            segment_id=6,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
        )
        self.assertEqual(bypass.inputs[0].recent_context, ())


def _observation(acceptance_kind):
    return UnifiedObservation(
        request_id="unified-session-1-segment-1",
        session_id="session-1",
        segment_id=1,
        status=UnifiedObservationStatus.OBSERVED,
        destination="experiment_pipeline",
        permission="forward_experiment_analysis",
        clarification_action="no_action",
        acceptance_kind=acceptance_kind,
    )


class UnifiedObservationEvidenceTests(unittest.TestCase):
    def test_structured_experiment_counts_as_experiment_evidence(self):
        self.assertTrue(
            _observation("structured_experiment").is_experiment_evidence
        )

    def test_degraded_note_counts_as_experiment_evidence(self):
        self.assertTrue(
            _observation("degraded_evidence_note").is_experiment_evidence
        )

    def test_no_acceptance_does_not_count_as_experiment_evidence(self):
        self.assertFalse(_observation(None).is_experiment_evidence)


if __name__ == "__main__":
    unittest.main()
