import unittest

from scripts.evaluate_unified_dispatch_bypass import (
    FIXED_TEXTS,
    build_fixed_observations,
)
from src.asr.schemas import ASRResult
from src.core.intent_policy import (
    IntentEvidence,
    IntentPolicyEvaluator,
)
from src.core.interaction_command import (
    InteractionCommand,
    InteractionCommandType,
)
from src.core.unified_dispatch_bypass import (
    UnifiedDispatchBypass,
    UnifiedDispatchBypassInput,
)
from src.llm.unified_router import UnifiedRouteResult


def make_asr_result(*, is_final=True):
    return ASRResult(
        asr_transcript="查看待确认问题。",
        asr_model_raw_text=(
            "<|zh|><|NEUTRAL|>查看待确认问题。"
        ),
        audio_path="fixed://one",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
        is_final=is_final,
    )


class RecordingRouter:
    def __init__(self, returned_text=None):
        self.returned_text = returned_text
        self.requests = []

    def route(self, request):
        self.requests.append(request)
        raw_text = self.returned_text or request.raw_text
        command = InteractionCommand(
            command_type=InteractionCommandType.REVIEW_PENDING,
            raw_text=raw_text,
            normalized_text="查看待确认问题",
        )
        return UnifiedRouteResult(
            exact_command=command,
            decision=IntentPolicyEvaluator.evaluate(
                InteractionCommandType.REVIEW_PENDING,
                IntentEvidence.EXACT_RULE,
            ),
        )


def make_input(asr_result=None):
    return UnifiedDispatchBypassInput(
        asr_result=asr_result or make_asr_result(),
        session_active=True,
        session_id="session-1",
        segment_id=1,
        pending_question_numbers=(1,),
        current_question_number=1,
    )


class UnifiedDispatchBypassTests(unittest.TestCase):
    def test_forwards_transcript_not_model_raw_text(self):
        router = RecordingRouter()
        evidence = make_asr_result()

        observation = UnifiedDispatchBypass(router).inspect(
            make_input(evidence)
        )

        self.assertEqual(len(router.requests), 1)
        self.assertEqual(
            router.requests[0].raw_text,
            evidence.asr_transcript,
        )
        self.assertNotEqual(
            router.requests[0].raw_text,
            evidence.asr_model_raw_text,
        )
        self.assertEqual(
            observation.plan.asr_transcript,
            evidence.asr_transcript,
        )

    def test_rejects_non_final_asr_evidence(self):
        with self.assertRaisesRegex(ValueError, "最终ASR结果"):
            make_input(make_asr_result(is_final=False))

    def test_rejects_router_text_replacement(self):
        bypass = UnifiedDispatchBypass(
            RecordingRouter(returned_text="被替换的文本")
        )

        with self.assertRaisesRegex(ValueError, "原样保留"):
            bypass.inspect(make_input())

    def test_observation_report_excludes_model_raw_text(self):
        observation = UnifiedDispatchBypass(
            RecordingRouter()
        ).inspect(make_input())

        report = observation.to_dict()

        self.assertIn("asr_transcript", report)
        self.assertNotIn("asr_model_raw_text", report)
        self.assertNotIn("route_result", report)

    def test_fixed_bypass_covers_five_expected_destinations(self):
        observations = build_fixed_observations()

        self.assertEqual(len(observations), len(FIXED_TEXTS))
        self.assertEqual(
            [item["destination"] for item in observations],
            [
                "experiment_pipeline",
                "clarification_context",
                "end_session_confirmation",
                "abstention",
                "degraded_note",
            ],
        )

    def test_fixed_failure_keeps_metrics_without_execution(self):
        failure = build_fixed_observations()[-1]

        self.assertTrue(failure["degraded"])
        self.assertEqual(failure["llm_attempts"], 2)
        self.assertEqual(
            failure["permission"],
            "forward_degraded_note",
        )


if __name__ == "__main__":
    unittest.main()
