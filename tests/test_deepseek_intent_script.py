import unittest

from scripts.test_deepseek_intent import CASES
from src.core.intent_classifier import IntentCandidateStatus
from src.core.intent_policy import IntentDisposition


class DeepSeekIntentScriptTests(unittest.TestCase):
    def test_fixed_cases_cover_required_smoke_paths(self):
        names = {case.name for case in CASES}

        self.assertEqual(len(CASES), 5)
        self.assertIn("普通实验口述", names)
        self.assertIn("自然查看问题", names)
        self.assertIn("自然结束候选", names)
        self.assertIn("语义不足时弃权", names)
        self.assertIn("指定问题答复候选", names)
        self.assertTrue(any(
            case.expected_status == IntentCandidateStatus.UNCERTAIN
            for case in CASES
        ))
        self.assertTrue(any(
            case.expected_disposition
            == IntentDisposition.REQUEST_CONFIRMATION
            for case in CASES
        ))


if __name__ == "__main__":
    unittest.main()
