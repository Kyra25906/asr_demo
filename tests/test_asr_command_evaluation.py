import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_asr_commands import (
    EvaluationDataError,
    evaluate_manifest,
    load_manifest,
)


class ASRCommandEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.audio = self.root / "sample.wav"
        self.audio.write_bytes(b"RIFF-test")

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_manifest(self, rows):
        path = self.root / "manifest.jsonl"
        path.write_text(
            "\n".join(
                json.dumps(row, ensure_ascii=False)
                for row in rows
            ),
            encoding="utf-8",
        )
        return path

    def sample(self, **overrides):
        row = {
            "sample_id": "sample-1",
            "audio_path": str(self.audio),
            "reference_text": "查看待确认问题。",
            "reference_status": "user_confirmed",
            "observed_asr_text": "看待确认问题。",
            "expected_intent": "review_pending",
            "session_id": "session-1",
            "segment_id": 1,
            "critical_terms": ["查看", "待确认问题"],
        }
        row.update(overrides)
        return row

    def test_counts_text_error_and_control_intent_miss_separately(self):
        report = evaluate_manifest([self.sample()])

        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(report["labeled_text_sample_count"], 1)
        self.assertEqual(report["exact_text_match_count"], 0)
        self.assertEqual(report["intent_match_count"], 0)
        self.assertEqual(report["control_command_miss_count"], 1)
        self.assertEqual(report["normal_content_false_trigger_count"], 0)

    def test_unlabeled_reference_is_excluded_from_text_accuracy(self):
        row = self.sample(
            reference_text=None,
            reference_status="needs_user_label",
        )
        report = evaluate_manifest([row])

        self.assertEqual(report["sample_count"], 1)
        self.assertEqual(report["labeled_text_sample_count"], 0)
        self.assertIsNone(report["exact_text_accuracy"])
        self.assertEqual(report["intent_sample_count"], 1)

    def test_counts_normal_content_false_trigger(self):
        row = self.sample(
            reference_text="结束实验记录。",
            observed_asr_text="结束实验记录。",
            expected_intent="normal",
        )
        report = evaluate_manifest([row])

        self.assertEqual(report["normal_content_false_trigger_count"], 1)
        self.assertEqual(report["intent_match_count"], 0)

    def test_load_manifest_rejects_missing_audio(self):
        path = self.write_manifest([
            self.sample(audio_path=str(self.root / "missing.wav"))
        ])

        with self.assertRaisesRegex(
            EvaluationDataError,
            "音频文件不存在",
        ):
            load_manifest(path)

    def test_load_manifest_rejects_unknown_intent(self):
        path = self.write_manifest([
            self.sample(expected_intent="delete_everything")
        ])

        with self.assertRaisesRegex(
            EvaluationDataError,
            "expected_intent",
        ):
            load_manifest(path)


if __name__ == "__main__":
    unittest.main()
