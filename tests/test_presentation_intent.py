import unittest
from dataclasses import FrozenInstanceError

from src.core.presentation_intent import (
    MessageKind,
    MessagePriority,
    PresentationIntent,
    ScreenTarget,
)


class PresentationIntentTests(unittest.TestCase):
    def test_builds_semantic_intent_without_final_text(self):
        intent = PresentationIntent(
            intent_id="record-3",
            kind=MessageKind.RECORD_ACK,
            args={"step_number": 3},
            priority=MessagePriority.ROUTINE,
            screen_target=ScreenTarget.STATUS,
            source_segment_id=4,
        )

        self.assertEqual(intent.args["step_number"], 3)
        self.assertFalse(hasattr(intent, "text"))
        self.assertFalse(hasattr(intent, "status"))

    def test_fields_cannot_be_reassigned(self):
        intent = self._build_intent()

        with self.assertRaises(FrozenInstanceError):
            intent.intent_id = "changed"

    def test_args_are_copied_and_cannot_be_mutated(self):
        supplied_args = {"step_number": 3}
        intent = self._build_intent(args=supplied_args)

        supplied_args["step_number"] = 9
        self.assertEqual(intent.args["step_number"], 3)
        with self.assertRaises(TypeError):
            intent.args["step_number"] = 10

    def test_rejects_empty_intent_id(self):
        with self.assertRaises(ValueError):
            self._build_intent(intent_id="  ")

    def test_rejects_non_positive_source_segment_id(self):
        with self.assertRaises(ValueError):
            self._build_intent(source_segment_id=0)

    def test_rejects_empty_argument_key(self):
        with self.assertRaises(ValueError):
            self._build_intent(args={"": 3})

    def test_debug_information_cannot_enter_presentation_intents(self):
        with self.assertRaises(ValueError):
            self._build_intent(kind=MessageKind.DEBUG)

    @staticmethod
    def _build_intent(**overrides):
        values = {
            "intent_id": "record-3",
            "kind": MessageKind.RECORD_ACK,
            "args": {"step_number": 3},
            "priority": MessagePriority.ROUTINE,
            "screen_target": ScreenTarget.STATUS,
            "source_segment_id": 4,
        }
        values.update(overrides)
        return PresentationIntent(**values)


if __name__ == "__main__":
    unittest.main()
