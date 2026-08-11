import unittest

from src.evaluation.term_postprocess_comparison import (
    compare_term_postprocess,
)


class FakeMatch:
    def __init__(self, original, replacement):
        self.original = original
        self.replacement = replacement

    def as_dict(self):
        return {"original": self.original, "replacement": self.replacement}


class FakeCorrector:
    def __init__(self, replacements):
        self.replacements = replacements

    def apply_text(self, text):
        corrected = text
        matches = []
        for wrong, right in self.replacements.items():
            if wrong in corrected:
                corrected = corrected.replace(wrong, right)
                matches.append(FakeMatch(wrong, right))
        return corrected, matches


def row(sample_id, reference, observed, expected_intent="normal"):
    return {
        "sample_id": sample_id,
        "audio_path": "unused.wav",
        "reference_text": reference,
        "reference_status": "user_confirmed",
        "observed_asr_text": observed,
        "expected_intent": expected_intent,
        "session_id": "s",
        "segment_id": 1,
        "critical_terms": [],
    }


class TermPostprocessComparisonTests(unittest.TestCase):
    def test_reports_term_and_text_improvement_without_overwriting_source(self):
        source = [row("one", "使用移液枪。", "使用一夜枪。")]

        report = compare_term_postprocess(
            source,
            corrector=FakeCorrector({"一夜枪": "移液枪"}),
            target_terms=("移液枪",),
            threshold=0.85,
        )

        self.assertEqual(source[0]["observed_asr_text"], "使用一夜枪。")
        self.assertEqual(report["baseline_target_term_hit_count"], 0)
        self.assertEqual(report["candidate_target_term_hit_count"], 1)
        self.assertEqual(report["text_improvements"], ["one"])
        self.assertEqual(report["text_regressions"], [])

    def test_reports_regression_on_unrelated_correct_text(self):
        source = [row("one", "记录水域。", "记录水域。")]

        report = compare_term_postprocess(
            source,
            corrector=FakeCorrector({"水域": "水浴"}),
            target_terms=("水浴",),
            threshold=0.85,
        )

        self.assertEqual(report["text_regressions"], ["one"])
        self.assertEqual(report["changed_sample_count"], 1)

    def test_reports_intent_change_separately_from_text_change(self):
        source = [row(
            "one", "结束实验记录。", "结束实验记绿。", "end_session"
        )]

        report = compare_term_postprocess(
            source,
            corrector=FakeCorrector({"记绿": "记录"}),
            target_terms=("实验记录",),
            threshold=0.85,
        )

        self.assertEqual(report["intent_improvements"], ["one"])
        self.assertEqual(report["intent_regressions"], [])

    def test_rejects_empty_or_duplicate_terms(self):
        for terms in ((), ("移液枪", "移液枪"), (" ",)):
            with self.subTest(terms=terms):
                with self.assertRaises(ValueError):
                    compare_term_postprocess(
                        [],
                        corrector=FakeCorrector({}),
                        target_terms=terms,
                        threshold=0.85,
                    )


if __name__ == "__main__":
    unittest.main()
