import unittest

from src.asr.schemas import ASRResult
from src.core.reply_coordinator import ReplyCoordinator
from src.core.unified_shadow import (
    ShadowObservationStatus,
    UnifiedShadowObserver,
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


def asr(text="加入缓冲液。"):
    return ASRResult(
        asr_transcript=text,
        asr_model_raw_text=f"raw:{text}",
        audio_path="fixed://shadow.wav",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )


class UnifiedShadowObserverTests(unittest.TestCase):
    def test_success_returns_redacted_summary_and_preserves_input(self):
        bypass = FakeBypass(result=Result())
        observation = UnifiedShadowObserver(bypass).observe(
            request_id="shadow-session-1-segment-2",
            session_id="session-1",
            segment_id=2,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
        )
        self.assertEqual(observation.status, ShadowObservationStatus.OBSERVED)
        self.assertEqual(observation.destination, "experiment_pipeline")
        self.assertEqual(observation.clarification_action, "create")
        self.assertEqual(observation.missing_fields, ("temperature",))
        self.assertTrue(observation.follow_up_required)
        self.assertEqual(bypass.inputs[0].asr_result.asr_transcript, "加入缓冲液。")
        self.assertFalse(hasattr(observation, "raw_text"))

    def test_failure_is_isolated_without_secret_error_detail(self):
        observation = UnifiedShadowObserver(
            FakeBypass(error=RuntimeError("secret transcript"))
        ).observe(
            request_id="shadow-session-1-segment-2",
            session_id="session-1",
            segment_id=2,
            asr_result=asr(),
            reply_coordinator=ReplyCoordinator(),
        )
        self.assertEqual(observation.status, ShadowObservationStatus.FAILED)
        self.assertEqual(observation.error_type, "RuntimeError")
        self.assertNotIn("secret", repr(observation))

    def test_snapshot_reads_context_without_mutating_coordinator(self):
        coordinator = ReplyCoordinator()
        before = coordinator.active_clarifications()
        bypass = FakeBypass(result=Result())
        UnifiedShadowObserver(bypass).observe(
            request_id="shadow-session-1-segment-3",
            session_id="session-1",
            segment_id=3,
            asr_result=asr(),
            reply_coordinator=coordinator,
        )
        self.assertEqual(coordinator.active_clarifications(), before)
        self.assertEqual(bypass.inputs[0].clarification_context.unresolved, before)


if __name__ == "__main__":
    unittest.main()
