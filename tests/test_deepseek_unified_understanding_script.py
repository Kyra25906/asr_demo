import unittest
from types import SimpleNamespace

from scripts.test_deepseek_unified_understanding import (
    CASES,
    result_matches,
)
from src.core.interaction_command import InteractionCommandType
from src.core.unified_understanding import UnifiedInputKind


class DeepSeekUnifiedUnderstandingScriptTests(unittest.TestCase):
    def test_fixed_cases_cover_all_branches_and_control_boundaries(self):
        self.assertEqual(len(CASES), 5)
        self.assertEqual(
            {case.expected_kind for case in CASES},
            set(UnifiedInputKind),
        )
        commands = {case.expected_command for case in CASES}
        self.assertIn(InteractionCommandType.END_SESSION, commands)
        self.assertIn(InteractionCommandType.TARGETED_ANSWER, commands)
        self.assertTrue(all(case.text.strip() for case in CASES))

    def test_matcher_rejects_degradation_or_wrong_control(self):
        case = next(
            item for item in CASES
            if item.expected_command == InteractionCommandType.END_SESSION
        )
        wrong_control = SimpleNamespace(
            intent=SimpleNamespace(
                command_type=InteractionCommandType.REVIEW_PENDING
            )
        )
        for degraded, kind, control in (
            (True, UnifiedInputKind.CONTROL, wrong_control),
            (False, UnifiedInputKind.UNCERTAIN, None),
            (False, UnifiedInputKind.CONTROL, wrong_control),
        ):
            with self.subTest(degraded=degraded, kind=kind):
                outcome = SimpleNamespace(
                    degraded=degraded,
                    value=SimpleNamespace(
                        input_kind=kind,
                        control=control,
                    ),
                )
                self.assertFalse(result_matches(case, outcome))


if __name__ == "__main__":
    unittest.main()
