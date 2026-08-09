import unittest

from src.core.interaction_command import InteractionCommandType
from src.core.reply_coordinator import ReplyCoordinator
from src.core.targeted_clarification import (
    TargetedAnswerStatus,
    resolve_targeted_answer,
)
from src.llm.schemas import (
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def add_question(
    coordinator: ReplyCoordinator,
    *,
    segment_id: int,
    missing_field: str,
    question: str,
) -> None:
    raw_text = f"第{segment_id}段实验操作。"
    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text=raw_text,
        missing_fields=[missing_field],
        source_session_id="session-1",
        source_segment_id=segment_id,
    )
    coordinator.ingest_analysis(
        segment_id=segment_id,
        raw_text=raw_text,
        analysis=LLMAnalysisResult(
            events=[event],
            should_ask_follow_up=True,
            follow_up_question=question,
        ),
    )


class TargetedClarificationTests(unittest.TestCase):
    def setUp(self):
        self.coordinator = ReplyCoordinator()
        add_question(
            self.coordinator,
            segment_id=1,
            missing_field="duration",
            question="离心多长时间？",
        )
        add_question(
            self.coordinator,
            segment_id=2,
            missing_field="temperature",
            question="水浴温度是多少？",
        )

    def test_resolves_existing_number_with_inline_answer(self):
        result = resolve_targeted_answer(
            "问题2，温度是60摄氏度。",
            reply_coordinator=self.coordinator,
        )

        self.assertEqual(result.status, TargetedAnswerStatus.READY)
        self.assertEqual(
            result.command_type,
            InteractionCommandType.TARGETED_ANSWER,
        )
        self.assertEqual(result.display_number, 2)
        self.assertEqual(result.clarification_id, "segment-2")
        self.assertEqual(result.answer_text, "温度是60摄氏度")
        self.assertFalse(result.confirms_suggestion)

    def test_detects_explicit_confirmation_inside_targeted_answer(self):
        result = resolve_targeted_answer(
            "问题2，是的，是水浴，温度60摄氏度。",
            reply_coordinator=self.coordinator,
        )

        self.assertEqual(result.status, TargetedAnswerStatus.READY)
        self.assertTrue(result.confirms_suggestion)

    def test_question_form_is_not_treated_as_confirmation(self):
        result = resolve_targeted_answer(
            "问题2，是否为水浴？",
            reply_coordinator=self.coordinator,
        )

        self.assertEqual(result.status, TargetedAnswerStatus.READY)
        self.assertFalse(result.confirms_suggestion)

    def test_reports_unknown_number_without_guessing(self):
        result = resolve_targeted_answer(
            "问题9，温度是60摄氏度。",
            reply_coordinator=self.coordinator,
        )

        self.assertEqual(result.status, TargetedAnswerStatus.NOT_FOUND)
        self.assertIsNone(result.clarification_id)

    def test_requires_answer_in_same_utterance(self):
        result = resolve_targeted_answer(
            "回答问题2。",
            reply_coordinator=self.coordinator,
        )

        self.assertEqual(
            result.status,
            TargetedAnswerStatus.MISSING_ANSWER,
        )
        self.assertEqual(result.display_number, 2)

    def test_normal_experiment_text_is_not_consumed(self):
        result = resolve_targeted_answer(
            "继续离心5分钟。",
            reply_coordinator=self.coordinator,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
