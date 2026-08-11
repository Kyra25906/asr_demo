import tempfile
import unittest
from pathlib import Path

from src.evaluation.command_corpus import (
    CommandCorpusPrompt,
    RecordingAttempt,
    RecordingStatus,
    SpokenTextStatus,
)
from src.evaluation.command_corpus_capture import (
    CommandCorpusCaptureCoordinator,
    ReviewDecision,
)
from src.evaluation.command_corpus_plan import CommandCorpusPlan
from src.evaluation.command_corpus_session import CommandCorpusCaptureSession
from src.evaluation.command_corpus_store import CommandCorpusStore


class FakeRecorder:
    def __init__(self, directory, outcomes):
        self.directory = Path(directory)
        self.outcomes = iter(outcomes)
        self.calls = 0

    def record_until_silence(self):
        self.calls += 1
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return self.directory / outcome


class CommandCorpusCaptureSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        self.attempts_path = self.directory / "attempts.jsonl"
        self.prompts = (
            CommandCorpusPrompt(
                sample_id="a",
                expected_intent="defer_current",
                prompt_text="这个先跳过。",
            ),
            CommandCorpusPrompt(
                sample_id="b",
                expected_intent="review_pending",
                prompt_text="查看待确认问题。",
            ),
        )
        self.plan = CommandCorpusPlan(schema_version=1, prompts=self.prompts)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_session(self, outcomes):
        recorder = FakeRecorder(self.directory, outcomes)
        store = CommandCorpusStore(self.attempts_path)
        coordinator = CommandCorpusCaptureCoordinator(
            recorder=recorder,
            player=lambda path: None,
            store=store,
        )
        session = CommandCorpusCaptureSession(
            plan=self.plan,
            attempts_path=self.attempts_path,
            coordinator=coordinator,
        )
        return session, recorder

    def run_session(self, session, decisions, retry=lambda outcome: False):
        decision_iter = iter(decisions)
        shown = []
        summary = session.run(
            before_capture=lambda prompt, attempt, position, total: shown.append(
                (prompt.sample_id, attempt, position, total)
            ),
            review=lambda prompt, path: next(decision_iter),
            retry_after_problem=retry,
        )
        return summary, shown

    def test_skips_previously_accepted_prompt_and_resumes_attempt_number(self):
        store = CommandCorpusStore(self.attempts_path)
        store.append(
            RecordingAttempt.from_prompt(
                self.prompts[0],
                attempt_number=2,
                status=RecordingStatus.ACCEPTED,
                audio_path=self.directory / "old.wav",
                spoken_text=self.prompts[0].prompt_text,
                spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
            )
        )
        session, recorder = self.make_session(["new.wav"])

        summary, shown = self.run_session(session, [ReviewDecision.ACCEPT])

        self.assertEqual(shown, [("b", 1, 1, 1)])
        self.assertEqual(recorder.calls, 1)
        self.assertEqual(summary.completed_before, 1)
        self.assertEqual(summary.completed_after, 2)
        self.assertEqual(summary.remaining_prompts, 0)

    def test_explicit_retry_creates_new_attempt_then_accepts(self):
        session, recorder = self.make_session(
            ["first.wav", "second.wav", "third.wav"]
        )

        summary, shown = self.run_session(
            session,
            [
                ReviewDecision.RETRY,
                ReviewDecision.ACCEPT,
                ReviewDecision.ACCEPT,
            ],
        )

        self.assertEqual(shown[:2], [("a", 1, 1, 2), ("a", 2, 1, 2)])
        self.assertEqual(recorder.calls, 3)
        self.assertEqual(summary.newly_completed, 2)

    def test_failure_can_retry_when_outer_policy_allows(self):
        session, recorder = self.make_session(
            [TimeoutError("timeout"), "a.wav", "b.wav"]
        )
        retries = iter([True])

        summary, shown = self.run_session(
            session,
            [ReviewDecision.ACCEPT, ReviewDecision.ACCEPT],
            retry=lambda outcome: next(retries),
        )

        self.assertEqual(shown[:2], [("a", 1, 1, 2), ("a", 2, 1, 2)])
        self.assertEqual(summary.completed_after, 2)

    def test_truncated_without_retry_remains_pending_in_summary(self):
        session, recorder = self.make_session(["a.wav", "b.wav"])

        summary, shown = self.run_session(
            session,
            [ReviewDecision.TRUNCATED, ReviewDecision.ACCEPT],
        )

        self.assertEqual(summary.completed_after, 1)
        self.assertEqual(summary.remaining_prompts, 1)

    def test_completed_plan_performs_no_recording(self):
        store = CommandCorpusStore(self.attempts_path)
        for prompt in self.prompts:
            store.append(
                RecordingAttempt.from_prompt(
                    prompt,
                    attempt_number=1,
                    status=RecordingStatus.ACCEPTED,
                    audio_path=self.directory / f"{prompt.sample_id}.wav",
                    spoken_text=prompt.prompt_text,
                    spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
                )
            )
        session, recorder = self.make_session([])

        summary, shown = self.run_session(session, [])

        self.assertEqual(shown, [])
        self.assertEqual(recorder.calls, 0)
        self.assertEqual(summary.remaining_prompts, 0)


if __name__ == "__main__":
    unittest.main()
