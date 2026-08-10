import unittest

from src.asr.schemas import ASRResult

from src.core.reply_coordinator import ReplyCoordinator
from src.llm.schemas import (
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.main import try_handle_confirmation_answer


class FakeStore:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def append(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error


def make_asr_result(text: str):
    return ASRResult(
        asr_transcript=text,
        asr_model_raw_text=f"raw:{text}",
        audio_path="audio/answer.wav",
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )


def make_coordinator_with_confirmation() -> ReplyCoordinator:
    coordinator = ReplyCoordinator()
    raw_text = "使用一液枪吸取500微生样品。"
    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text="使用移液枪吸取500微升样品。",
        needs_confirmation=True,
        confirmation_reason="疑似ASR错词",
        source_session_id="session_001",
        source_segment_id=7,
    )
    coordinator.ingest_analysis(
        segment_id=7,
        raw_text=raw_text,
        analysis=LLMAnalysisResult(
            events=[event],
            should_ask_follow_up=True,
            follow_up_question="请确认是否为移液枪和500微升？",
        ),
    )
    return coordinator


class ConfirmationMainTests(unittest.TestCase):
    def test_success_saves_raw_asr_then_record_and_commits(self):
        coordinator = make_coordinator_with_confirmation()
        asr_store = FakeStore()
        confirmation_store = FakeStore()

        resolution = try_handle_confirmation_answer(
            asr_result=make_asr_result(
                "是的，是移液枪和500微升。"
            ),
            session_id="session_001",
            segment_id=8,
            reply_coordinator=coordinator,
            asr_store=asr_store,
            confirmation_store=confirmation_store,
        )

        self.assertIsNotNone(resolution)
        self.assertTrue(resolution.fully_resolved)
        self.assertEqual(len(asr_store.calls), 1)
        self.assertEqual(len(confirmation_store.calls), 1)
        record = confirmation_store.calls[0][0][0]
        self.assertEqual(record.answer_raw_text, "是的，是移液枪和500微升。")
        self.assertEqual(record.answer_audio_path, "audio/answer.wav")
        self.assertEqual(coordinator.active_clarifications(), ())

    def test_normal_experiment_text_is_not_saved_as_confirmation(self):
        coordinator = make_coordinator_with_confirmation()
        asr_store = FakeStore()
        confirmation_store = FakeStore()

        resolution = try_handle_confirmation_answer(
            asr_result=make_asr_result("继续搅拌十分钟。"),
            session_id="session_001",
            segment_id=8,
            reply_coordinator=coordinator,
            asr_store=asr_store,
            confirmation_store=confirmation_store,
        )

        self.assertIsNone(resolution)
        self.assertEqual(asr_store.calls, [])
        self.assertEqual(confirmation_store.calls, [])
        self.assertEqual(len(coordinator.active_clarifications()), 1)

    def test_confirmation_store_failure_keeps_pending_and_raw_asr(self):
        coordinator = make_coordinator_with_confirmation()
        asr_store = FakeStore()
        confirmation_store = FakeStore(
            error=OSError("模拟确认文件写入失败")
        )

        with self.assertRaises(OSError):
            try_handle_confirmation_answer(
                asr_result=make_asr_result("是的。"),
                session_id="session_001",
                segment_id=8,
                reply_coordinator=coordinator,
                asr_store=asr_store,
                confirmation_store=confirmation_store,
            )

        self.assertEqual(len(asr_store.calls), 1)
        self.assertEqual(len(coordinator.active_clarifications()), 1)
        self.assertTrue(
            coordinator.active_clarifications()[0].requires_confirmation
        )

    def test_asr_store_failure_does_not_write_confirmation_or_commit(self):
        coordinator = make_coordinator_with_confirmation()
        asr_store = FakeStore(
            error=OSError("模拟ASR文件写入失败")
        )
        confirmation_store = FakeStore()

        with self.assertRaises(OSError):
            try_handle_confirmation_answer(
                asr_result=make_asr_result("确认。"),
                session_id="session_001",
                segment_id=8,
                reply_coordinator=coordinator,
                asr_store=asr_store,
                confirmation_store=confirmation_store,
            )

        self.assertEqual(confirmation_store.calls, [])
        self.assertEqual(len(coordinator.active_clarifications()), 1)


if __name__ == "__main__":
    unittest.main()
