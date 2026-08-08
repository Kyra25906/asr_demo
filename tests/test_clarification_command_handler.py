import unittest
from types import SimpleNamespace

from src.core.clarification_command_handler import (
    try_handle_clarification_command,
)
from src.core.interaction_command import InteractionCommandType
from src.core.pending_clarification import ClarificationStatus
from src.core.reply_coordinator import ReplyCoordinator
from src.llm.schemas import (
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


class FakeStore:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def append(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error


def make_asr_result(text: str):
    return SimpleNamespace(text=text)


def make_coordinator_with_current_question() -> ReplyCoordinator:
    coordinator = ReplyCoordinator()
    raw_text = "将样品离心。"
    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text=raw_text,
        missing_fields=["duration"],
        source_session_id="session-1",
        source_segment_id=1,
    )
    coordinator.ingest_analysis(
        segment_id=1,
        raw_text=raw_text,
        analysis=LLMAnalysisResult(
            events=[event],
            should_ask_follow_up=True,
            follow_up_question="离心多长时间？",
        ),
    )
    coordinator.pop_next_reply()
    return coordinator


class ClarificationCommandHandlerTests(unittest.TestCase):
    def test_defer_saves_raw_asr_then_changes_state(self):
        coordinator = make_coordinator_with_current_question()
        store = FakeStore()

        result = try_handle_clarification_command(
            asr_result=make_asr_result("这个先跳过。"),
            session_id="session-1",
            segment_id=2,
            reply_coordinator=coordinator,
            asr_store=store,
        )

        self.assertEqual(
            result.command_type,
            InteractionCommandType.DEFER_CURRENT,
        )
        self.assertEqual(len(store.calls), 1)
        self.assertEqual(
            result.deferred.status,
            ClarificationStatus.DEFERRED,
        )

    def test_store_failure_does_not_defer_question(self):
        coordinator = make_coordinator_with_current_question()
        store = FakeStore(error=OSError("模拟写入失败"))

        with self.assertRaises(OSError):
            try_handle_clarification_command(
                asr_result=make_asr_result("稍后再问"),
                session_id="session-1",
                segment_id=2,
                reply_coordinator=coordinator,
                asr_store=store,
            )

        current = coordinator.current_clarification()
        self.assertIsNotNone(current)
        self.assertEqual(
            current.status,
            ClarificationStatus.ACTIVE,
        )

    def test_defer_without_current_question_is_still_saved(self):
        coordinator = ReplyCoordinator()
        store = FakeStore()

        result = try_handle_clarification_command(
            asr_result=make_asr_result("这个先跳过"),
            session_id="session-1",
            segment_id=1,
            reply_coordinator=coordinator,
            asr_store=store,
        )

        self.assertIsNone(result.deferred)
        self.assertEqual(len(store.calls), 1)

    def test_review_returns_active_and_deferred_questions(self):
        coordinator = make_coordinator_with_current_question()
        coordinator.defer_current(segment_id=2)
        store = FakeStore()

        result = try_handle_clarification_command(
            asr_result=make_asr_result("查看待确认问题"),
            session_id="session-1",
            segment_id=3,
            reply_coordinator=coordinator,
            asr_store=store,
        )

        self.assertEqual(
            result.command_type,
            InteractionCommandType.REVIEW_PENDING,
        )
        self.assertEqual(len(result.unresolved), 1)
        self.assertEqual(
            result.unresolved[0].status,
            ClarificationStatus.DEFERRED,
        )
        self.assertEqual(len(store.calls), 1)

    def test_normal_experiment_text_is_not_handled_or_saved(self):
        coordinator = make_coordinator_with_current_question()
        store = FakeStore()

        result = try_handle_clarification_command(
            asr_result=make_asr_result("继续离心五分钟。"),
            session_id="session-1",
            segment_id=2,
            reply_coordinator=coordinator,
            asr_store=store,
        )

        self.assertIsNone(result)
        self.assertEqual(store.calls, [])


if __name__ == "__main__":
    unittest.main()
