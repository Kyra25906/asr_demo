import unittest
from pathlib import Path

from scripts.compare_asr_languages import (
    compare_languages,
    validate_languages,
)
from src.asr.schemas import ASRResult


class FakeRecognizer:
    def __init__(self, texts):
        self.texts = texts
        self.calls = []

    def recognize(self, audio_path, *, language):
        self.calls.append((Path(audio_path), language))
        text = self.texts[language]
        return ASRResult(
            text=text,
            raw_text=f"raw:{text}",
            audio_path=str(audio_path),
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fake",
            language=language,
            is_final=True,
        )


class ASRLanguageComparisonTests(unittest.TestCase):
    def sample(self):
        return {
            "sample_id": "sample-1",
            "audio_path": "sample.wav",
            "reference_text": "查看待确认问题。",
            "reference_status": "user_confirmed",
            "observed_asr_text": "旧结果不得被修改。",
            "expected_intent": "review_pending",
            "session_id": "session-1",
            "segment_id": 1,
            "critical_terms": ["查看"],
        }

    def test_compares_same_audio_in_requested_language_order(self):
        row = self.sample()
        recognizer = FakeRecognizer({
            "auto": "看待确认问题。",
            "zh": "查看待确认问题。",
        })

        report = compare_languages(
            [row],
            recognizer=recognizer,
            languages=("auto", "zh"),
        )

        self.assertEqual(
            recognizer.calls,
            [(Path("sample.wav"), "auto"), (Path("sample.wav"), "zh")],
        )
        self.assertEqual(
            report["candidates"]["auto"]["metrics"]["exact_text_match_count"],
            0,
        )
        self.assertEqual(
            report["candidates"]["zh"]["metrics"]["exact_text_match_count"],
            1,
        )
        self.assertEqual(row["observed_asr_text"], "旧结果不得被修改。")

    def test_keeps_raw_recognition_and_timing_for_audit(self):
        report = compare_languages(
            [self.sample()],
            recognizer=FakeRecognizer({"zh": "查看待确认问题。"}),
            languages=("zh",),
        )

        item = report["candidates"]["zh"]["recognitions"][0]
        self.assertEqual(item["raw_text"], "raw:查看待确认问题。")
        self.assertEqual(item["recognition_seconds"], 0.1)

    def test_rejects_unsupported_or_duplicate_languages(self):
        with self.assertRaisesRegex(ValueError, "不支持"):
            validate_languages(["auto", "Chinese"])
        with self.assertRaisesRegex(ValueError, "不能重复"):
            validate_languages(["zh", "zh"])


if __name__ == "__main__":
    unittest.main()
