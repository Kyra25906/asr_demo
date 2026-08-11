import json
import tempfile
import unittest
from pathlib import Path

from src.asr.schemas import ASRResult

from src.evaluation.command_corpus_baseline import (
    CaptureBaselineError,
    build_capture_baseline,
    load_accepted_attempts,
)
from src.evaluation.command_corpus_plan import CommandCorpusPlan
from src.evaluation.command_corpus import CommandCorpusPrompt


class FakeRecognizer:
    def __init__(self, texts):
        self.texts = texts
        self.calls = []

    def recognize(self, audio_path, *, language="auto"):
        self.calls.append((audio_path, language))
        text = self.texts[audio_path.name]
        return ASRResult(
            asr_transcript=text,
            asr_model_raw_text=f"raw:{text}",
            audio_path=str(audio_path),
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fake-asr",
            language=language,
        )


class CommandCorpusBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.wav1 = root / "one.wav"
        self.wav2 = root / "two.wav"
        self.wav1.write_bytes(b"wav1")
        self.wav2.write_bytes(b"wav2")
        self.plan = CommandCorpusPlan(1, (
            CommandCorpusPrompt("one", "review_pending", "查看问题。"),
            CommandCorpusPrompt("two", "normal", "记录溶液。"),
        ))

    def tearDown(self):
        self.temp.cleanup()

    def row(self, sample_id, audio_path, **overrides):
        data = {
            "sample_id": sample_id,
            "status": "accepted",
            "audio_path": str(audio_path),
            "spoken_text": "查看问题。" if sample_id == "one" else "记录溶液。",
            "spoken_text_status": "user_confirmed",
            "attempt_id": f"{sample_id}:attempt:1",
        }
        data.update(overrides)
        return data

    def test_loads_only_unique_user_confirmed_accepted_records(self):
        path = Path(self.temp.name) / "attempts.jsonl"
        rows = [
            {**self.row("one", self.wav1), "status": "retry_requested"},
            self.row("one", self.wav1),
            self.row("two", self.wav2),
        ]
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )

        accepted = load_accepted_attempts(path)

        self.assertEqual(set(accepted), {"one", "two"})

    def test_rejects_duplicate_accepted_or_missing_wav(self):
        for rows, expected in (
            ([self.row("one", self.wav1)] * 2, "多条accepted"),
            ([self.row("one", Path(self.temp.name) / "missing.wav")], "WAV不存在"),
        ):
            with self.subTest(expected=expected):
                path = Path(self.temp.name) / f"{expected}.jsonl"
                path.write_text(
                    "".join(json.dumps(row) + "\n" for row in rows),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(CaptureBaselineError, expected):
                    load_accepted_attempts(path)

    def test_recognizes_in_plan_order_and_computes_metrics(self):
        accepted = {
            "two": self.row("two", self.wav2),
            "one": self.row("one", self.wav1),
        }
        recognizer = FakeRecognizer({
            "one.wav": "查看问题。",
            "two.wav": "记录溶液。",
        })

        rows, metrics = build_capture_baseline(
            self.plan, accepted, recognizer=recognizer
        )

        self.assertEqual([row["sample_id"] for row in rows], ["one", "two"])
        self.assertEqual(metrics["exact_text_match_count"], 2)
        self.assertEqual(metrics["normal_content_false_trigger_count"], 0)
        self.assertEqual(metrics["reference_intent_match_count"], 1)
        self.assertEqual(metrics["rule_coverage_miss_count"], 1)
        self.assertEqual(metrics["asr_induced_intent_miss_count"], 0)
        self.assertEqual([path.name for path, _ in recognizer.calls], ["one.wav", "two.wav"])

    def test_rejects_incomplete_plan_evidence_before_recognition(self):
        recognizer = FakeRecognizer({})

        with self.assertRaisesRegex(CaptureBaselineError, "缺少"):
            build_capture_baseline(
                self.plan,
                {"one": self.row("one", self.wav1)},
                recognizer=recognizer,
            )

        self.assertEqual(recognizer.calls, [])


if __name__ == "__main__":
    unittest.main()
