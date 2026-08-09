import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace

from src.core.reply_coordinator import ReplyCoordinator
from src.core.session_processing_queue import CompletedSegment
from src.llm.processor import ProcessOutcome
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.main import display_completed_segments


def make_completed_segment(
    *,
    segment_id: int,
    raw_text: str,
    missing_fields: list[str] | None = None,
    question: str | None = None,
    entities: ExperimentEntities | None = None,
) -> CompletedSegment:
    missing_fields = missing_fields or []
    should_ask = bool(missing_fields)
    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text=raw_text,
        entities=entities or ExperimentEntities(),
        missing_fields=missing_fields,
        source_session_id="session_001",
        source_segment_id=segment_id,
    )
    outcome = ProcessOutcome(
        value=LLMAnalysisResult(
            events=[event],
            should_ask_follow_up=should_ask,
            follow_up_question=question if should_ask else None,
            assistant_reply=None,
        ),
        degraded=False,
        llm_attempts=1,
        llm_processing_seconds=0.1,
    )
    asr_result = SimpleNamespace(
        text=raw_text,
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
    )
    return CompletedSegment(
        segment_id=segment_id,
        asr_result=asr_result,
        outcome=outcome,
        error=None,
    )


class ReplyCoordinatorIntegrationTests(unittest.TestCase):
    def test_batch_displays_at_most_one_reply(self):
        coordinator = ReplyCoordinator()
        completed = [
            make_completed_segment(
                segment_id=1,
                raw_text="第一段加热。",
                missing_fields=["duration"],
                question="第一段持续多长时间？",
            ),
            make_completed_segment(
                segment_id=2,
                raw_text="第二段加热。",
                missing_fields=["temperature"],
                question="第二段温度是多少？",
            ),
        ]

        first_output = io.StringIO()
        with redirect_stdout(first_output):
            display_completed_segments(
                completed,
                reply_coordinator=coordinator,
            )

        self.assertEqual(
            first_output.getvalue().count("\n待确认："),
            1,
        )
        self.assertIn("关于第 1 段", first_output.getvalue())
        self.assertNotIn("关于第 2 段", first_output.getvalue())

        second_output = io.StringIO()
        with redirect_stdout(second_output):
            display_completed_segments(
                [],
                reply_coordinator=coordinator,
            )

        self.assertIn("关于第 2 段", second_output.getvalue())

    def test_later_segment_updates_old_question(self):
        coordinator = ReplyCoordinator()
        with redirect_stdout(io.StringIO()):
            display_completed_segments(
                [
                    make_completed_segment(
                        segment_id=3,
                        raw_text="将溶液加热。",
                        missing_fields=["temperature", "duration"],
                        question="温度和时间是多少？",
                    )
                ],
                reply_coordinator=coordinator,
            )

        output = io.StringIO()
        with redirect_stdout(output):
            display_completed_segments(
                [
                    make_completed_segment(
                        segment_id=4,
                        raw_text="温度为60摄氏度。",
                        entities=ExperimentEntities(
                            temperature="60摄氏度"
                        ),
                    )
                ],
                reply_coordinator=coordinator,
            )

        self.assertIn("关于第 3 段", output.getvalue())
        self.assertIn("仍需确认：时间", output.getvalue())

    def test_background_error_does_not_create_question(self):
        coordinator = ReplyCoordinator()
        failed = CompletedSegment(
            segment_id=1,
            asr_result=SimpleNamespace(
                text="原始文本。",
                audio_duration_seconds=1.0,
                recognition_seconds=0.1,
            ),
            outcome=None,
            error="OSError: 模拟存储失败",
        )

        with redirect_stdout(io.StringIO()):
            display_completed_segments(
                [failed],
                reply_coordinator=coordinator,
            )

        self.assertEqual(coordinator.active_clarifications(), ())
        self.assertIsNone(coordinator.pop_next_reply())

    def test_targeted_answer_updates_only_selected_question(self):
        coordinator = ReplyCoordinator()
        with redirect_stdout(io.StringIO()):
            display_completed_segments(
                [
                    make_completed_segment(
                        segment_id=1,
                        raw_text="将样品离心。",
                        missing_fields=["duration"],
                        question="离心多长时间？",
                    ),
                    make_completed_segment(
                        segment_id=2,
                        raw_text="将溶液水浴加热。",
                        missing_fields=["duration"],
                        question="水浴多长时间？",
                    ),
                ],
                reply_coordinator=coordinator,
            )

        answer = make_completed_segment(
            segment_id=3,
            raw_text="问题2，加热10分钟。",
            entities=ExperimentEntities(duration="10分钟"),
        )
        answer = CompletedSegment(
            segment_id=answer.segment_id,
            asr_result=answer.asr_result,
            outcome=answer.outcome,
            error=answer.error,
            target_clarification_id="segment-2",
        )

        with redirect_stdout(io.StringIO()):
            display_completed_segments(
                [answer],
                reply_coordinator=coordinator,
            )

        unresolved = coordinator.active_clarifications()
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].clarification_id, "segment-1")

    def test_explicit_targeted_answer_clears_confirmation(self):
        coordinator = ReplyCoordinator()
        raw_text = "将样品放在水域中加热。"
        event = ExperimentEvent(
            event_type=ExperimentEventType.OPERATION,
            raw_text=raw_text,
            normalized_text="将样品放在水浴中加热。",
            entities=ExperimentEntities(instrument="水浴"),
            missing_fields=["temperature", "duration"],
            needs_confirmation=True,
            confirmation_reason="水域疑似为水浴",
            source_session_id="session_001",
            source_segment_id=1,
        )
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text=raw_text,
            analysis=LLMAnalysisResult(
                events=[event],
                should_ask_follow_up=True,
                follow_up_question=(
                    "请确认是水浴，并补充温度和时间。"
                ),
            ),
        )

        answer = make_completed_segment(
            segment_id=2,
            raw_text="问题1，是的，是水浴，60度10分钟。",
            entities=ExperimentEntities(
                instrument="水浴",
                temperature="60摄氏度",
                duration="10分钟",
            ),
        )
        answer = CompletedSegment(
            segment_id=answer.segment_id,
            asr_result=answer.asr_result,
            outcome=answer.outcome,
            error=answer.error,
            target_clarification_id="segment-1",
            confirms_target_suggestion=True,
        )

        with redirect_stdout(io.StringIO()):
            display_completed_segments(
                [answer],
                reply_coordinator=coordinator,
            )

        self.assertEqual(coordinator.active_clarifications(), ())


if __name__ == "__main__":
    unittest.main()
