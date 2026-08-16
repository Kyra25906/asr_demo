import unittest

from src.core.presentation_coordinator import (
    PresentationCoordinator,
    coordinate,
)
from src.core.presentation_intent import (
    MessageKind,
    MessagePriority,
    PresentationIntent,
    ScreenTarget,
)


def _record_ack(intent_id="r", step_number=1):
    return PresentationIntent(
        intent_id=intent_id,
        kind=MessageKind.RECORD_ACK,
        args={"result": "recorded", "step_number": step_number},
        priority=MessagePriority.ROUTINE,
        screen_target=ScreenTarget.STATUS,
    )


def _clarification(intent_id="q", priority=MessagePriority.ACTIVE_QUESTION):
    return PresentationIntent(
        intent_id=intent_id,
        kind=MessageKind.CLARIFICATION,
        args={"question": f"问题{intent_id}"},
        priority=priority,
        screen_target=ScreenTarget.CURRENT_QUESTION,
    )


def _deferred(intent_id="d"):
    return PresentationIntent(
        intent_id=intent_id,
        kind=MessageKind.CLARIFICATION_DEFERRED,
        args={"display_number": 1},
        priority=MessagePriority.DIRECT_ACK,
        screen_target=ScreenTarget.STATUS,
    )


class CoordinateTests(unittest.TestCase):
    def test_empty_input(self):
        deliver, deferred = coordinate(())

        self.assertEqual(deliver, ())
        self.assertEqual(deferred, ())

    def test_fifo_preserves_order(self):
        first = _record_ack("r1", 1)
        question = _clarification("q1")
        second = _record_ack("r2", 2)

        deliver, deferred = coordinate([first, question, second])

        self.assertEqual(deliver, (first, question, second))
        self.assertEqual(deferred, ())

    def test_adjacent_duplicate_is_merged(self):
        first = _record_ack("r1", 3)
        duplicate = _record_ack("r2", 3)  # 不同 id，相同语义

        deliver, _ = coordinate([first, duplicate])

        self.assertEqual(deliver, (first,))

    def test_non_adjacent_duplicate_is_kept(self):
        first = _record_ack("r1", 3)
        question = _clarification("q1")
        duplicate = _record_ack("r2", 3)

        deliver, _ = coordinate([first, question, duplicate])

        self.assertEqual(deliver, (first, question, duplicate))

    def test_single_question_passes_through(self):
        question = _clarification("q1")

        deliver, deferred = coordinate([question])

        self.assertEqual(deliver, (question,))
        self.assertEqual(deferred, ())

    def test_multiple_questions_keep_highest_priority(self):
        lower = _clarification("low", priority=MessagePriority.REVIEW)
        higher = _clarification(
            "high", priority=MessagePriority.ACTIVE_QUESTION
        )

        deliver, deferred = coordinate([lower, higher])

        self.assertEqual(deliver, (higher,))
        self.assertEqual(deferred, (lower,))

    def test_multiple_questions_defer_the_rest_and_preserve_others(self):
        record = _record_ack("r1", 1)
        lower = _clarification("low", priority=MessagePriority.REVIEW)
        higher = _clarification(
            "high", priority=MessagePriority.ACTIVE_QUESTION
        )
        deferred_ack = _deferred("d1")

        deliver, deferred = coordinate(
            [record, lower, higher, deferred_ack]
        )

        self.assertEqual(deliver, (record, higher, deferred_ack))
        self.assertEqual(deferred, (lower,))

    def test_tie_priority_keeps_first_question(self):
        first = _clarification("q1")
        second = _clarification("q2")

        deliver, deferred = coordinate([first, second])

        self.assertEqual(deliver, (first,))
        self.assertEqual(deferred, (second,))


class CoordinatorQueueTests(unittest.TestCase):
    def test_submit_then_drain_returns_all(self):
        coordinator = PresentationCoordinator()
        first = _record_ack("r1", 1)
        question = _clarification("q1")
        second = _record_ack("r2", 2)

        coordinator.submit([first, question, second])

        self.assertEqual(coordinator.drain(), (first, question, second))
        self.assertEqual(coordinator.pending_count, 0)

    def test_deferred_question_is_returned_next_drain(self):
        coordinator = PresentationCoordinator()
        first_question = _clarification("q1")
        second_question = _clarification("q2")

        coordinator.submit([first_question, second_question])

        self.assertEqual(coordinator.drain(), (first_question,))
        self.assertEqual(coordinator.pending_count, 1)

        self.assertEqual(coordinator.drain(), (second_question,))
        self.assertEqual(coordinator.pending_count, 0)

    def test_drain_empty_times_out_to_empty(self):
        coordinator = PresentationCoordinator()

        self.assertEqual(coordinator.drain(timeout=0.01), ())

    def test_pending_count_reflects_queue(self):
        coordinator = PresentationCoordinator()

        self.assertEqual(coordinator.pending_count, 0)
        coordinator.submit([_record_ack("r1", 1)])
        self.assertEqual(coordinator.pending_count, 1)

    def test_join_waits_for_drained_intent_to_be_marked_complete(self):
        coordinator = PresentationCoordinator()
        coordinator.submit([_record_ack("r1", 1)])

        self.assertEqual(coordinator.unfinished_count, 1)
        self.assertEqual(len(coordinator.drain()), 1)
        self.assertEqual(coordinator.pending_count, 0)
        self.assertFalse(coordinator.join(timeout=0.01))

        coordinator.mark_completed()

        self.assertTrue(coordinator.join(timeout=0.01))
        self.assertEqual(coordinator.unfinished_count, 0)

    def test_adjacent_duplicate_is_accounted_without_mark_completed(self):
        coordinator = PresentationCoordinator()
        coordinator.submit((
            _record_ack("r1", 1),
            _record_ack("r2", 1),
        ))

        delivered = coordinator.drain()

        self.assertEqual(len(delivered), 1)
        self.assertEqual(coordinator.unfinished_count, 1)
        coordinator.mark_completed()
        self.assertTrue(coordinator.join(timeout=0.01))

    def test_deferred_question_remains_unfinished_until_next_delivery(self):
        coordinator = PresentationCoordinator()
        coordinator.submit(
            _clarification(name)
            for name in ("q1", "q2")
        )

        self.assertEqual(len(coordinator.drain()), 1)
        coordinator.mark_completed()
        self.assertEqual(coordinator.pending_count, 1)
        self.assertEqual(coordinator.unfinished_count, 1)
        self.assertFalse(coordinator.join(timeout=0.01))

        self.assertEqual(len(coordinator.drain()), 1)
        coordinator.mark_completed()
        self.assertTrue(coordinator.join(timeout=0.01))

    def test_mark_completed_rejects_unbalanced_call(self):
        coordinator = PresentationCoordinator()

        with self.assertRaises(RuntimeError):
            coordinator.mark_completed()


if __name__ == "__main__":
    unittest.main()
