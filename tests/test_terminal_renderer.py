import unittest

from src.core.presentation_copy import RecordAckResult
from src.core.presentation_intent import PresentationIntent
from src.core.presentation_message import (
    MessageKind,
    MessagePriority,
    ScreenTarget,
)
from src.core.terminal_renderer import TerminalRenderer


def _record_ack_intent(source_segment_id=4):
    return PresentationIntent(
        intent_id="i-1",
        kind=MessageKind.RECORD_ACK,
        args={"result": RecordAckResult.RECORDED, "step_number": 3},
        priority=MessagePriority.ROUTINE,
        screen_target=ScreenTarget.STATUS,
        source_segment_id=source_segment_id,
    )


class TerminalRendererTests(unittest.TestCase):
    def test_render_user_uses_plain_language(self):
        renderer = TerminalRenderer(ui_mode="user")

        text = renderer.render(_record_ack_intent())

        self.assertEqual(text, "已记录实验步骤 3。")

    def test_render_admin_includes_source_reference(self):
        renderer = TerminalRenderer(ui_mode="admin")

        text = renderer.render(_record_ack_intent())

        self.assertEqual(text, "已记录实验步骤 3（来源口述 4）。")

    def test_render_review_is_multiline(self):
        renderer = TerminalRenderer(ui_mode="user")
        intent = PresentationIntent(
            intent_id="i-2",
            kind=MessageKind.CLARIFICATION_REVIEW,
            args={"items": ()},
            priority=MessagePriority.REVIEW,
            screen_target=ScreenTarget.DIALOGUE,
        )

        text = renderer.render(intent)

        self.assertEqual(text, "当前没有待确认问题。")

    def test_ui_mode_is_exposed(self):
        renderer = TerminalRenderer(ui_mode="admin")

        self.assertEqual(renderer.ui_mode, "admin")

    def test_invalid_ui_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            TerminalRenderer(ui_mode="developer")


if __name__ == "__main__":
    unittest.main()
