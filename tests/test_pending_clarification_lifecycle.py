import unittest

from src.core.pending_clarification import (
    ClarificationStatus,
    PendingClarification,
)
from src.core.reply_coordinator import ReplyCoordinator
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def make_clarification() -> PendingClarification:
    return PendingClarification(
        clarification_id="clarification-1",
        display_number=1,
        source_segment_id=1,
        source_raw_text="将样品离心。",
        question="离心多长时间？",
        missing_fields=("duration",),
    )


def make_analysis(
    *,
    segment_id: int,
    raw_text: str,
    duration: str | None = None,
    ask_duration: bool = False,
) -> LLMAnalysisResult:
    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text=raw_text,
        entities=ExperimentEntities(duration=duration),
        missing_fields=["duration"] if ask_duration else [],
        source_session_id="session-1",
        source_segment_id=segment_id,
    )
    return LLMAnalysisResult(
        events=[event],
        should_ask_follow_up=ask_duration,
        follow_up_question=(
            "需要多长时间？" if ask_duration else None
        ),
        assistant_reply=None,
    )


class PendingClarificationLifecycleTests(unittest.TestCase):
    def test_defer_keeps_question_unresolved(self):
        deferred = make_clarification().defer(segment_id=2)

        self.assertEqual(
            deferred.status,
            ClarificationStatus.DEFERRED,
        )
        self.assertTrue(deferred.is_unresolved)
        self.assertFalse(deferred.is_active)
        self.assertFalse(deferred.reply_pending)

    def test_reactivate_preserves_display_number(self):
        deferred = make_clarification().defer(segment_id=2)
        reactivated = deferred.reactivate(segment_id=3)

        self.assertEqual(
            reactivated.status,
            ClarificationStatus.ACTIVE,
        )
        self.assertEqual(reactivated.display_number, 1)
        self.assertTrue(reactivated.reply_pending)

    def test_expire_keeps_history_but_is_not_unresolved(self):
        expired = make_clarification().expire(segment_id=2)

        self.assertEqual(
            expired.status,
            ClarificationStatus.EXPIRED,
        )
        self.assertFalse(expired.is_unresolved)
        self.assertEqual(expired.missing_fields, ("duration",))

    def test_deferred_question_can_be_resolved_by_later_field(self):
        deferred = make_clarification().defer(segment_id=2)
        resolved = deferred.supply_fields(
            {"duration"},
            segment_id=3,
        )

        self.assertEqual(
            resolved.status,
            ClarificationStatus.RESOLVED,
        )
        self.assertFalse(resolved.is_unresolved)

    def test_non_active_question_cannot_wait_for_reply(self):
        with self.assertRaises(ValueError):
            PendingClarification(
                clarification_id="clarification-1",
                display_number=1,
                source_segment_id=1,
                source_raw_text="将样品离心。",
                question="离心多长时间？",
                missing_fields=("duration",),
                status=ClarificationStatus.DEFERRED,
                reply_pending=True,
            )


class ReplyCoordinatorLifecycleTests(unittest.TestCase):
    def _register_question(
        self,
        coordinator: ReplyCoordinator,
        *,
        segment_id: int,
    ) -> None:
        raw_text = f"第{segment_id}步离心。"
        coordinator.ingest_analysis(
            segment_id=segment_id,
            raw_text=raw_text,
            analysis=make_analysis(
                segment_id=segment_id,
                raw_text=raw_text,
                ask_duration=True,
            ),
        )

    def test_created_question_can_be_deferred(self):
        coordinator = ReplyCoordinator()
        self._register_question(coordinator, segment_id=1)

        # 统一链下创建即交付（立即显示），可直接暂缓，无需 pop_next_reply。
        deferred = coordinator.defer_current(segment_id=2)

        self.assertIsNotNone(deferred)
        self.assertEqual(
            deferred.status,
            ClarificationStatus.DEFERRED,
        )

    def test_deferred_question_does_not_block_new_question(self):
        coordinator = ReplyCoordinator()
        self._register_question(coordinator, segment_id=1)
        coordinator.pop_next_reply()
        coordinator.defer_current(segment_id=2)

        self._register_question(coordinator, segment_id=3)
        reply = coordinator.pop_next_reply()

        self.assertIsNotNone(reply)
        self.assertEqual(reply.source_segment_id, 3)
        unresolved = coordinator.active_clarifications()
        self.assertEqual(len(unresolved), 2)
        self.assertEqual(
            unresolved[0].status,
            ClarificationStatus.DEFERRED,
        )

    def test_display_numbers_are_stable_and_not_reused(self):
        coordinator = ReplyCoordinator()
        self._register_question(coordinator, segment_id=1)
        first = coordinator.pop_next_reply()
        coordinator.defer_current(segment_id=2)
        self._register_question(coordinator, segment_id=3)

        unresolved = coordinator.active_clarifications()

        self.assertEqual(first.clarification_id, "segment-1")
        self.assertEqual(
            [item.display_number for item in unresolved],
            [1, 2],
        )

    def test_reactivated_question_returns_to_reply_queue(self):
        coordinator = ReplyCoordinator()
        self._register_question(coordinator, segment_id=1)
        coordinator.pop_next_reply()
        coordinator.defer_current(segment_id=2)

        reactivated = coordinator.reactivate_question(
            display_number=1,
            segment_id=3,
        )
        reply = coordinator.pop_next_reply()

        self.assertIsNotNone(reactivated)
        self.assertEqual(reactivated.display_number, 1)
        self.assertIsNotNone(reply)
        self.assertEqual(reply.source_segment_id, 1)


if __name__ == "__main__":
    unittest.main()
