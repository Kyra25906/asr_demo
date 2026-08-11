import unittest
import json
import tempfile
from pathlib import Path

from src.evaluation.command_corpus import (
    CommandCorpusPrompt,
    RecordingAttempt,
    RecordingStatus,
    SpokenTextStatus,
)
from src.evaluation.command_corpus_store import CommandCorpusStore


class CommandCorpusPromptTests(unittest.TestCase):
    def test_builds_immutable_prompt_with_normalized_terms(self):
        prompt = CommandCorpusPrompt(
            sample_id="review-pending-001",
            expected_intent="review_pending",
            prompt_text="查看待确认问题。",
            critical_terms=("查看", "待确认问题"),
        )

        self.assertEqual(prompt.critical_terms, ("查看", "待确认问题"))
        with self.assertRaises(AttributeError):
            prompt.prompt_text = "修改后的文字"

    def test_rejects_empty_identity_or_prompt(self):
        for field, value in (
            ("sample_id", "  "),
            ("prompt_text", ""),
        ):
            values = {
                "sample_id": "sample-1",
                "expected_intent": "review_pending",
                "prompt_text": "查看待确认问题。",
            }
            values[field] = value
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    CommandCorpusPrompt(**values)

    def test_rejects_unknown_intent(self):
        with self.assertRaisesRegex(ValueError, "expected_intent"):
            CommandCorpusPrompt(
                sample_id="sample-1",
                expected_intent="erase_database",
                prompt_text="删除全部记录。",
            )


class RecordingAttemptTests(unittest.TestCase):
    def setUp(self):
        self.prompt = CommandCorpusPrompt(
            sample_id="review-pending-001",
            expected_intent="review_pending",
            prompt_text="查看待确认问题。",
        )

    def test_accepted_recording_can_wait_for_manual_review(self):
        attempt = RecordingAttempt.from_prompt(
            self.prompt,
            attempt_number=1,
            status=RecordingStatus.ACCEPTED,
            audio_path=Path("audio/evaluation/sample.wav"),
        )

        self.assertEqual(
            attempt.spoken_text_status,
            SpokenTextStatus.AWAITING_REVIEW,
        )
        self.assertFalse(attempt.baseline_eligible)

    def test_user_confirmed_recording_is_baseline_eligible(self):
        attempt = RecordingAttempt.from_prompt(
            self.prompt,
            attempt_number=2,
            status=RecordingStatus.ACCEPTED,
            audio_path=Path("audio/evaluation/sample.wav"),
            spoken_text="查看待确认问题。",
            spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
            observed_asr_text="查看待确认问题。",
        )

        self.assertTrue(attempt.baseline_eligible)
        data = attempt.to_dict()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(data["spoken_text_status"], "user_confirmed")
        self.assertEqual(data["audio_path"], "audio/evaluation/sample.wav")

    def test_retry_keeps_bad_take_for_diagnosis(self):
        attempt = RecordingAttempt.from_prompt(
            self.prompt,
            attempt_number=1,
            status=RecordingStatus.RETRY_REQUESTED,
            audio_path=Path("audio/evaluation/bad-take.wav"),
            capture_note="句首被截断",
        )

        self.assertEqual(attempt.capture_note, "句首被截断")
        self.assertFalse(attempt.baseline_eligible)

    def test_rejects_non_positive_attempt_number(self):
        with self.assertRaisesRegex(ValueError, "attempt_number"):
            RecordingAttempt.from_prompt(
                self.prompt,
                attempt_number=0,
                status=RecordingStatus.SKIPPED,
            )

    def test_accepted_recording_requires_audio_path(self):
        with self.assertRaisesRegex(ValueError, "audio_path"):
            RecordingAttempt.from_prompt(
                self.prompt,
                attempt_number=1,
                status=RecordingStatus.ACCEPTED,
            )

    def test_confirmed_text_requires_spoken_text(self):
        with self.assertRaisesRegex(ValueError, "spoken_text"):
            RecordingAttempt.from_prompt(
                self.prompt,
                attempt_number=1,
                status=RecordingStatus.ACCEPTED,
                audio_path=Path("sample.wav"),
                spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
            )

    def test_failed_attempt_requires_error_and_is_not_eligible(self):
        with self.assertRaisesRegex(ValueError, "error"):
            RecordingAttempt.from_prompt(
                self.prompt,
                attempt_number=1,
                status=RecordingStatus.FAILED,
            )

        failed = RecordingAttempt.from_prompt(
            self.prompt,
            attempt_number=1,
            status=RecordingStatus.FAILED,
            error="TimeoutError: 未检测到人声",
        )
        self.assertFalse(failed.baseline_eligible)

    def test_skipped_attempt_cannot_claim_confirmed_speech(self):
        with self.assertRaisesRegex(ValueError, "SKIPPED"):
            RecordingAttempt.from_prompt(
                self.prompt,
                attempt_number=1,
                status=RecordingStatus.SKIPPED,
                spoken_text="查看待确认问题。",
                spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
            )


class CommandCorpusStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.temp_dir.name) / "attempts.jsonl"
        self.prompt = CommandCorpusPrompt(
            sample_id="review-pending-001",
            expected_intent="review_pending",
            prompt_text="查看待确认问题。",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_attempt(self, attempt_number=1):
        return RecordingAttempt.from_prompt(
            self.prompt,
            attempt_number=attempt_number,
            status=RecordingStatus.ACCEPTED,
            audio_path=Path(f"audio/take-{attempt_number}.wav"),
        )

    def test_appends_utf8_record_with_stable_attempt_id(self):
        store = CommandCorpusStore(self.output_path)
        store.append(self.make_attempt())

        stored = json.loads(
            self.output_path.read_text(encoding="utf-8").strip()
        )
        self.assertEqual(
            stored["attempt_id"],
            "review-pending-001:attempt:1",
        )
        self.assertEqual(stored["prompt_text"], "查看待确认问题。")
        self.assertIn("saved_at", stored)

    def test_allows_new_attempt_number_for_same_prompt(self):
        store = CommandCorpusStore(self.output_path)
        store.append(self.make_attempt(1))
        store.append(self.make_attempt(2))

        self.assertEqual(
            len(self.output_path.read_text(encoding="utf-8").splitlines()),
            2,
        )

    def test_rejects_duplicate_attempt_without_second_write(self):
        store = CommandCorpusStore(self.output_path)
        attempt = self.make_attempt()
        store.append(attempt)
        original = self.output_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "attempt_id"):
            store.append(attempt)

        self.assertEqual(self.output_path.read_bytes(), original)

    def test_invalid_existing_json_is_not_overwritten(self):
        original = "这不是JSON\n"
        self.output_path.write_text(original, encoding="utf-8")
        store = CommandCorpusStore(self.output_path)

        with self.assertRaisesRegex(ValueError, "第 1 行"):
            store.append(self.make_attempt())

        self.assertEqual(
            self.output_path.read_text(encoding="utf-8"),
            original,
        )

    def test_replace_failure_keeps_original_and_removes_temp_file(self):
        store = CommandCorpusStore(self.output_path)
        store.append(self.make_attempt(1))
        original = self.output_path.read_bytes()

        def fail_replace(source, destination):
            raise OSError("simulated replace failure")

        failing_store = CommandCorpusStore(
            self.output_path,
            replace_func=fail_replace,
        )
        with self.assertRaisesRegex(OSError, "simulated"):
            failing_store.append(self.make_attempt(2))

        self.assertEqual(self.output_path.read_bytes(), original)
        temporary_files = list(
            self.output_path.parent.glob(".attempts.jsonl.*.tmp")
        )
        self.assertEqual(temporary_files, [])

    def test_output_path_cannot_be_directory(self):
        directory_path = Path(self.temp_dir.name) / "attempts"
        directory_path.mkdir()
        store = CommandCorpusStore(directory_path)

        with self.assertRaisesRegex(ValueError, "不是文件"):
            store.append(self.make_attempt())


if __name__ == "__main__":
    unittest.main()
