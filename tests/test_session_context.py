import unittest

from src.core.session_context import (
    SessionContext,
)
from src.llm.schemas import (
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def make_event(
    *,
    event_type: ExperimentEventType,
    raw_text: str,
    normalized_text: str,
) -> ExperimentEvent:
    return ExperimentEvent(
        event_type=event_type,
        raw_text=raw_text,
        normalized_text=normalized_text,
        source_session_id="session_001",
        source_segment_id=1,
    )


def make_analysis(
    *events: ExperimentEvent,
) -> LLMAnalysisResult:
    return LLMAnalysisResult(
        events=list(events)
    )


class SessionContextTests(
    unittest.TestCase
):
    def test_new_context_is_empty(
        self,
    ):
        context = SessionContext(
            max_events=3
        )

        self.assertEqual(
            len(context),
            0,
        )
        self.assertEqual(
            context.as_prompt_context(),
            (),
        )

    def test_normal_event_uses_normalized_text(
        self,
    ):
        context = SessionContext(
            max_events=3
        )

        event = make_event(
            event_type=(
                ExperimentEventType.OPERATION
            ),
            raw_text=(
                "加入五百微升缓冲液。"
            ),
            normalized_text=(
                "加入500微升缓冲液。"
            ),
        )

        context.add_analysis(
            make_analysis(event)
        )

        self.assertEqual(
            context.as_prompt_context(),
            (
                "[operation] "
                "加入500微升缓冲液。",
            ),
        )

    def test_note_event_uses_raw_text(
        self,
    ):
        context = SessionContext(
            max_events=3
        )

        event = make_event(
            event_type=(
                ExperimentEventType.NOTE
            ),
            raw_text=(
                "使用营业枪加入缓冲液。"
            ),
            normalized_text=(
                "使用移液枪加入缓冲液。"
            ),
        )

        context.add_analysis(
            make_analysis(event)
        )

        self.assertEqual(
            context.as_prompt_context(),
            (
                "[note] "
                "使用营业枪加入缓冲液。",
            ),
        )

    def test_context_keeps_only_latest_events(
        self,
    ):
        context = SessionContext(
            max_events=2
        )

        first = make_event(
            event_type=(
                ExperimentEventType.OPERATION
            ),
            raw_text="第一步。",
            normalized_text="第一步。",
        )

        second = make_event(
            event_type=(
                ExperimentEventType.OBSERVATION
            ),
            raw_text="第二步。",
            normalized_text="第二步。",
        )

        third = make_event(
            event_type=(
                ExperimentEventType.MEASUREMENT
            ),
            raw_text="第三步。",
            normalized_text="第三步。",
        )

        context.add_analysis(
            make_analysis(
                first,
                second,
                third,
            )
        )

        self.assertEqual(
            context.as_prompt_context(),
            (
                "[observation] 第二步。",
                "[measurement] 第三步。",
            ),
        )

    def test_clear_removes_all_events(
        self,
    ):
        context = SessionContext(
            max_events=3
        )

        event = make_event(
            event_type=(
                ExperimentEventType.OPERATION
            ),
            raw_text="加入缓冲液。",
            normalized_text="加入缓冲液。",
        )

        context.add_analysis(
            make_analysis(event)
        )

        context.clear()

        self.assertEqual(
            len(context),
            0,
        )
        self.assertEqual(
            context.as_prompt_context(),
            (),
        )


if __name__ == "__main__":
    unittest.main()