import unittest

from src.core.presentation_copy import (
    ConfirmationAckResult,
    RecordAckResult,
    ReviewItem,
    copy_for_intent,
)
from src.core.presentation_intent import PresentationIntent
from src.core.presentation_message import (
    MessageKind,
    MessagePriority,
    ScreenTarget,
)


def _make_intent(kind, *, args, source_segment_id=4, screen_target=None):
    return PresentationIntent(
        intent_id="i-1",
        kind=kind,
        args=args,
        priority=MessagePriority.ROUTINE,
        screen_target=screen_target or ScreenTarget.STATUS,
        source_segment_id=source_segment_id,
    )


class RecordAckCopyTests(unittest.TestCase):
    def test_user_copy_for_recorded_step(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.RECORDED, "step_number": 3},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "已记录实验步骤 3。")

    def test_admin_copy_includes_internal_source_reference(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.RECORDED, "step_number": 3},
        )

        text = copy_for_intent(intent, ui_mode="admin")

        self.assertEqual(text, "已记录实验步骤 3（来源口述 4）。")

    def test_degraded_copy_uses_plain_language(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.DEGRADED},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "原始记录已保存，结构化处理暂时不可用。")

    def test_failed_copy_confirms_that_raw_record_was_saved(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.FAILED},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "本段结构化处理失败，原始记录已保存。")

    def test_missing_result_is_rejected(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_unknown_result_is_rejected(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": "unknown"},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_recorded_step_requires_positive_integer(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.RECORDED, "step_number": 0},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_unknown_ui_mode_is_rejected(self):
        intent = _make_intent(
            MessageKind.RECORD_ACK,
            args={"result": RecordAckResult.DEGRADED},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="developer")

    def test_unsupported_message_kind_is_rejected(self):
        intent = _make_intent(
            MessageKind.SAFETY_ALERT,
            args={},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")


class ClarificationCopyTests(unittest.TestCase):
    def test_question_stands_alone_without_dev_prefix(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION,
            args={"question": "第2步需要离心多长时间？"},
            screen_target=ScreenTarget.CURRENT_QUESTION,
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "小科：第2步需要离心多长时间？")

    def test_admin_appends_source_without_double_punctuation(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION,
            args={"question": "第2步需要离心多长时间？"},
            screen_target=ScreenTarget.CURRENT_QUESTION,
        )

        text = copy_for_intent(intent, ui_mode="admin")

        self.assertEqual(text, "小科：第2步需要离心多长时间？（来源口述 4）")

    def test_missing_question_is_rejected(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION,
            args={},
            screen_target=ScreenTarget.CURRENT_QUESTION,
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_blank_question_is_rejected(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION,
            args={"question": "  "},
            screen_target=ScreenTarget.CURRENT_QUESTION,
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")


class ConfirmationAckCopyTests(unittest.TestCase):
    def test_answered_with_remaining_fields_translates_field_names(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.ANSWERED,
                "display_number": 1,
                "remaining_fields": ("temperature", "duration"),
            },
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "已补充问题 1，仍需补充：温度、时间。")

    def test_answered_resolved_uses_plain_ack(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.ANSWERED,
                "display_number": 1,
                "resolved": True,
            },
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "已补充问题 1，问题已解决。")

    def test_answered_without_fields_needs_confirmation(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.ANSWERED,
                "display_number": 1,
            },
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "已补充问题 1，仍需确认。")

    def test_confirmed_uses_plain_ack(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.CONFIRMED,
                "display_number": 2,
            },
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "已确认问题 2。")

    def test_missing_result_is_rejected(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={"display_number": 1},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_unknown_result_is_rejected(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={"result": "deferred", "display_number": 1},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_missing_display_number_is_rejected(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={"result": ConfirmationAckResult.CONFIRMED},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_non_positive_display_number_is_rejected(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.CONFIRMED,
                "display_number": 0,
            },
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_answered_requires_bool_resolved(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.ANSWERED,
                "display_number": 1,
                "resolved": "yes",
            },
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_answered_requires_tuple_remaining_fields(self):
        intent = _make_intent(
            MessageKind.CONFIRMATION_ACK,
            args={
                "result": ConfirmationAckResult.ANSWERED,
                "display_number": 1,
                "remaining_fields": ["temperature"],
            },
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")


class DeferredCopyTests(unittest.TestCase):
    def test_deferred_uses_plain_ack(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION_DEFERRED,
            args={"display_number": 3},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "问题 3 已暂缓。")


class ReviewCopyTests(unittest.TestCase):
    def test_empty_review_uses_plain_language(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION_REVIEW,
            args={"items": ()},
            screen_target=ScreenTarget.DIALOGUE,
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "当前没有待确认问题。")

    def test_review_lists_items_with_status(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION_REVIEW,
            args={
                "items": (
                    ReviewItem(
                        display_number=1,
                        is_deferred=False,
                        question="离心多长时间？",
                    ),
                    ReviewItem(
                        display_number=2,
                        is_deferred=True,
                        question="温度是多少？",
                    ),
                ),
            },
            screen_target=ScreenTarget.DIALOGUE,
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(
            text,
            "当前共有 2 个待确认问题：\n"
            "- 问题 1（待回答）：离心多长时间？\n"
            "- 问题 2（已暂缓）：温度是多少？",
        )

    def test_review_rejects_non_tuple_items(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION_REVIEW,
            args={"items": [ReviewItem(1, False, "q")]},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_review_rejects_non_review_item(self):
        intent = _make_intent(
            MessageKind.CLARIFICATION_REVIEW,
            args={"items": ("not-a-review-item",)},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")

    def test_review_item_rejects_non_positive_number(self):
        with self.assertRaises(ValueError):
            ReviewItem(display_number=0, is_deferred=False, question="q")


class PassthroughCopyTests(unittest.TestCase):
    def test_stage_summary_passthrough_text(self):
        intent = _make_intent(
            MessageKind.STAGE_SUMMARY,
            args={"text": "系统将立即继续监听。"},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "系统将立即继续监听。")

    def test_transcript_passthrough_text(self):
        intent = _make_intent(
            MessageKind.TRANSCRIPT,
            args={"text": "本段 ASR 识别完成：加入缓冲液"},
        )

        text = copy_for_intent(intent, ui_mode="user")

        self.assertEqual(text, "本段 ASR 识别完成：加入缓冲液")

    def test_passthrough_requires_text(self):
        intent = _make_intent(
            MessageKind.TRANSCRIPT,
            args={},
        )

        with self.assertRaises(ValueError):
            copy_for_intent(intent, ui_mode="user")


if __name__ == "__main__":
    unittest.main()
