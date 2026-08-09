import tempfile
import unittest
from pathlib import Path

from src.evaluation.command_corpus import (
    CommandCorpusPrompt,
    RecordingStatus,
    SpokenTextStatus,
)
from src.evaluation.command_corpus_capture import (
    CommandCorpusCaptureCoordinator,
    ReviewDecision,
)


class FakeRecorder:
    def __init__(self, path=None, error=None):
        self.path = path
        self.error = error

    def record_until_silence(self):
        if self.error:
            raise self.error
        return self.path


class FakeStore:
    def __init__(self):
        self.attempts = []

    def append(self, attempt):
        self.attempts.append(attempt)


class CommandCorpusCaptureCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audio_path = Path(self.temp_dir.name) / "take.wav"
        self.prompt = CommandCorpusPrompt(
            sample_id="sample-1",
            expected_intent="defer_current",
            prompt_text="这个先跳过。",
        )
        self.store = FakeStore()

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_coordinator(self, *, recorder=None, player=None):
        return CommandCorpusCaptureCoordinator(
            recorder=recorder or FakeRecorder(self.audio_path),
            player=player or (lambda path: None),
            store=self.store,
        )

    def capture(self, decision, **kwargs):
        return self.make_coordinator(**kwargs).capture_once(
            prompt=self.prompt,
            attempt_number=1,
            review=lambda path: decision,
        )

    def test_accept_saves_confirmed_original_sentence(self):
        outcome = self.capture(ReviewDecision.ACCEPT)

        self.assertEqual(outcome.attempt.status, RecordingStatus.ACCEPTED)
        self.assertEqual(
            outcome.attempt.spoken_text_status,
            SpokenTextStatus.USER_CONFIRMED,
        )
        self.assertEqual(outcome.attempt.spoken_text, "这个先跳过。")
        self.assertFalse(outcome.should_retry)

    def test_truncated_and_duplicated_keep_wav_without_claiming_text(self):
        for decision in (
            ReviewDecision.TRUNCATED,
            ReviewDecision.DUPLICATED,
        ):
            with self.subTest(decision=decision):
                self.store.attempts.clear()
                outcome = self.capture(decision)
                self.assertEqual(
                    outcome.attempt.status,
                    RecordingStatus.RETRY_REQUESTED,
                )
                self.assertIsNone(outcome.attempt.spoken_text)
                self.assertEqual(outcome.attempt.audio_path, self.audio_path.resolve())

    def test_explicit_retry_requests_another_take(self):
        outcome = self.capture(ReviewDecision.RETRY)

        self.assertTrue(outcome.should_retry)
        self.assertEqual(outcome.attempt.status, RecordingStatus.RETRY_REQUESTED)

    def test_skip_keeps_audio_evidence_but_does_not_retry(self):
        outcome = self.capture(ReviewDecision.SKIP)

        self.assertEqual(outcome.attempt.status, RecordingStatus.SKIPPED)
        self.assertEqual(outcome.attempt.audio_path, self.audio_path.resolve())
        self.assertFalse(outcome.should_retry)

    def test_recording_failure_is_saved_without_fake_audio_path(self):
        outcome = self.capture(
            ReviewDecision.ACCEPT,
            recorder=FakeRecorder(error=TimeoutError("timeout")),
        )

        self.assertEqual(outcome.attempt.status, RecordingStatus.FAILED)
        self.assertIsNone(outcome.attempt.audio_path)
        self.assertIn("TimeoutError", outcome.attempt.error)

    def test_playback_failure_preserves_wav_and_skips_review(self):
        reviewed = []
        coordinator = self.make_coordinator(
            player=lambda path: (_ for _ in ()).throw(OSError("speaker"))
        )

        outcome = coordinator.capture_once(
            prompt=self.prompt,
            attempt_number=1,
            review=lambda path: reviewed.append(path),
        )

        self.assertEqual(reviewed, [])
        self.assertEqual(outcome.attempt.status, RecordingStatus.RETRY_REQUESTED)
        self.assertEqual(outcome.attempt.audio_path, self.audio_path.resolve())
        self.assertIn("即时回放失败", outcome.attempt.capture_note)

    def test_every_outcome_is_appended_exactly_once(self):
        self.capture(ReviewDecision.ACCEPT)

        self.assertEqual(len(self.store.attempts), 1)


if __name__ == "__main__":
    unittest.main()
