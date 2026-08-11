import unittest
from dataclasses import FrozenInstanceError, replace

from src.asr.schemas import ASRResult
from src.core.interaction_command import InteractionCommandType
from src.core.unified_dispatch import (
    UnifiedDispatchDestination,
    UnifiedDispatchPermission,
    UnifiedDispatchPlanner,
)
from src.core.unified_dispatch_execution import (
    DispatchExecutionRequest,
    DispatchExecutionResult,
    DispatchExecutionStatus,
    FakeDispatchExecutor,
)
from tests.test_unified_dispatch import control_route, exact_route


def build_request(
    *,
    request_id="request-1",
    command_type=InteractionCommandType.REVIEW_PENDING,
    transcript="用户忠实转写。",
    plan=None,
):
    if plan is None:
        plan = UnifiedDispatchPlanner.plan(
            exact_route(command_type, raw_text=transcript)
        )
    evidence = ASRResult(
        asr_transcript=transcript,
        asr_model_raw_text=f"<|zh|>{transcript}",
        audio_path="fixed://evidence.wav",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )
    return DispatchExecutionRequest(
        request_id=request_id,
        session_id="session-1",
        segment_id=1,
        asr_evidence=evidence,
        plan=plan,
    )


class DispatchExecutionContractTests(unittest.TestCase):
    def test_request_binds_identity_evidence_plan_and_is_immutable(self):
        request = build_request()
        self.assertEqual(
            request.permission,
            UnifiedDispatchPermission.FORWARD_CONTEXT_CANDIDATE,
        )
        with self.assertRaises(FrozenInstanceError):
            request.request_id = "replacement"

    def test_request_rejects_mismatched_or_non_final_asr_evidence(self):
        request = build_request()
        wrong_text = replace(
            request.asr_evidence,
            asr_transcript="被替换的文本。",
        )
        with self.assertRaisesRegex(ValueError, "原文不一致"):
            replace(request, asr_evidence=wrong_text)
        with self.assertRaisesRegex(ValueError, "最终ASR"):
            replace(
                request,
                asr_evidence=replace(request.asr_evidence, is_final=False),
            )

    def test_result_copies_request_identity_and_does_not_infer_side_effects(self):
        request = build_request()
        result = DispatchExecutionResult.from_request(
            request,
            status=DispatchExecutionStatus.ACCEPTED,
            reason="已接收。",
        )
        self.assertEqual(result.request_id, request.request_id)
        self.assertFalse(result.state_changed)
        self.assertFalse(result.persisted)
        self.assertEqual(result.produced_message_ids, ())

    def test_non_accepted_result_cannot_claim_side_effects(self):
        request = build_request()
        with self.assertRaisesRegex(ValueError, "不能声称"):
            DispatchExecutionResult.from_request(
                request,
                status=DispatchExecutionStatus.REJECTED,
                reason="拒绝。",
                persisted=True,
            )

    def test_result_rejects_destination_permission_mismatch(self):
        request = build_request()
        with self.assertRaisesRegex(ValueError, "目标与最小权限不匹配"):
            DispatchExecutionResult(
                request_id=request.request_id,
                session_id=request.session_id,
                segment_id=request.segment_id,
                destination=UnifiedDispatchDestination.ABSTENTION,
                permission=(
                    UnifiedDispatchPermission.FORWARD_CONTEXT_CANDIDATE
                ),
                status=DispatchExecutionStatus.REJECTED,
                state_changed=False,
                persisted=False,
                reason="非法组合。",
            )

    def test_no_action_permission_has_only_one_legal_status(self):
        no_action_plan = UnifiedDispatchPlanner.plan(control_route(
            InteractionCommandType.TARGETED_ANSWER,
            target_question_number=2,
            answer_text="五分钟",
        ))
        request = build_request(
            plan=no_action_plan,
        )
        with self.assertRaisesRegex(ValueError, "必须返回no_action"):
            DispatchExecutionResult.from_request(
                request,
                status=DispatchExecutionStatus.REJECTED,
                reason="错误状态。",
            )
        result = FakeDispatchExecutor().execute(request)
        self.assertEqual(result.status, DispatchExecutionStatus.NO_ACTION)

    def test_fake_rejects_permission_it_was_not_given(self):
        result = FakeDispatchExecutor().execute(build_request())
        self.assertEqual(result.status, DispatchExecutionStatus.REJECTED)
        self.assertFalse(result.state_changed)

    def test_fake_can_accept_without_pretending_to_execute(self):
        permission = UnifiedDispatchPermission.FORWARD_CONTEXT_CANDIDATE
        executor = FakeDispatchExecutor(
            accepted_permissions=frozenset({permission})
        )
        result = executor.execute(build_request())
        self.assertEqual(result.status, DispatchExecutionStatus.ACCEPTED)
        self.assertFalse(result.persisted)
        self.assertFalse(result.state_changed)

    def test_fake_failure_is_explicit_and_has_no_side_effect_claim(self):
        executor = FakeDispatchExecutor(
            accepted_permissions=frozenset({
                UnifiedDispatchPermission.FORWARD_CONTEXT_CANDIDATE
            }),
            failing_request_ids=frozenset({"request-1"}),
        )
        result = executor.execute(build_request())
        self.assertEqual(result.status, DispatchExecutionStatus.FAILED)
        self.assertFalse(result.persisted)

    def test_same_request_id_is_idempotent_but_collision_is_rejected(self):
        executor = FakeDispatchExecutor(
            accepted_permissions=frozenset({
                UnifiedDispatchPermission.FORWARD_CONTEXT_CANDIDATE
            })
        )
        request = build_request()
        first = executor.execute(request)
        second = executor.execute(request)
        self.assertIs(first, second)
        self.assertEqual(executor.execution_attempts, 1)

        collision = build_request(
            request_id=request.request_id,
            transcript="另一段忠实转写。",
        )
        with self.assertRaisesRegex(ValueError, "不同执行请求"):
            executor.execute(collision)
        self.assertEqual(executor.execution_attempts, 1)


if __name__ == "__main__":
    unittest.main()
