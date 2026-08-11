import json
import tempfile
import unittest
from pathlib import Path

from src.config import PROJECT_DIR
from src.evaluation.command_corpus_plan import (
    CommandCorpusPlan,
    load_capture_progress,
)


class CommandCorpusPlanTests(unittest.TestCase):
    def write_plan(self, directory, data):
        path = Path(directory) / "plan.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def valid_data(self):
        return {
            "schema_version": 1,
            "prompts": [
                {
                    "sample_id": "sample-1",
                    "expected_intent": "defer_current",
                    "prompt_text": "这个先跳过。",
                    "critical_terms": ["这个", "跳过"],
                }
            ],
        }

    def test_loads_versioned_plan(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = CommandCorpusPlan.load(
                self.write_plan(directory, self.valid_data())
            )

        self.assertEqual(plan.schema_version, 1)
        self.assertEqual(plan.prompts[0].sample_id, "sample-1")

    def test_rejects_extra_fields_and_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            extra = self.valid_data()
            extra["unexpected"] = True
            with self.assertRaisesRegex(ValueError, "额外字段"):
                CommandCorpusPlan.load(self.write_plan(directory, extra))

            duplicate = self.valid_data()
            duplicate["prompts"] = duplicate["prompts"] * 2
            with self.assertRaisesRegex(ValueError, "sample_id不能重复"):
                CommandCorpusPlan.load(self.write_plan(directory, duplicate))

    def test_rejects_unknown_intent_or_invalid_critical_terms(self):
        with tempfile.TemporaryDirectory() as directory:
            unknown = self.valid_data()
            unknown["prompts"][0]["expected_intent"] = "delete_all"
            with self.assertRaisesRegex(ValueError, "expected_intent"):
                CommandCorpusPlan.load(self.write_plan(directory, unknown))

            invalid = self.valid_data()
            invalid["prompts"][0]["critical_terms"] = "跳过"
            with self.assertRaisesRegex(ValueError, "字符串数组"):
                CommandCorpusPlan.load(self.write_plan(directory, invalid))

    def test_official_control_plan_contains_24_prompts(self):
        plan = CommandCorpusPlan.load(
            PROJECT_DIR / "evaluation" / "asr_commands" / "capture_plan.json"
        )

        self.assertEqual(len(plan.prompts), 24)
        self.assertEqual(
            {prompt.expected_intent for prompt in plan.prompts},
            {
                "review_pending",
                "defer_current",
                "end_session",
                "targeted_answer",
                "affirm",
                "deny",
                "normal",
            },
        )


class CaptureProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp_dir.name)
        plan_data = {
            "schema_version": 1,
            "prompts": [
                {"sample_id":"a","expected_intent":"defer_current","prompt_text":"这个先跳过。"},
                {"sample_id":"b","expected_intent":"review_pending","prompt_text":"查看待确认问题。"},
            ],
        }
        path = self.directory / "plan.json"
        path.write_text(json.dumps(plan_data, ensure_ascii=False), encoding="utf-8")
        self.plan = CommandCorpusPlan.load(path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def write_attempts(self, records):
        path = self.directory / "attempts.jsonl"
        path.write_text(
            "\n".join(json.dumps(record) for record in records),
            encoding="utf-8",
        )
        return path

    def test_only_accepted_prompt_is_skipped_on_resume(self):
        progress = load_capture_progress(
            self.plan,
            self.write_attempts(
                [
                    {"sample_id":"a","attempt_number":1,"status":"retry_requested"},
                    {"sample_id":"a","attempt_number":2,"status":"accepted"},
                    {"sample_id":"b","attempt_number":1,"status":"failed"},
                ]
            ),
        )

        self.assertEqual(progress.completed_sample_ids, {"a"})
        self.assertEqual([item.sample_id for item in progress.pending_prompts], ["b"])
        self.assertEqual(progress.next_attempt_numbers, {"a": 3, "b": 2})

    def test_missing_attempt_file_keeps_every_prompt_pending(self):
        progress = load_capture_progress(
            self.plan,
            self.directory / "missing.jsonl",
        )

        self.assertEqual(len(progress.pending_prompts), 2)
        self.assertEqual(progress.next_attempt_numbers, {"a": 1, "b": 1})

    def test_rejects_unknown_sample_or_invalid_attempt(self):
        with self.assertRaisesRegex(ValueError, "计划外sample_id"):
            load_capture_progress(
                self.plan,
                self.write_attempts(
                    [{"sample_id":"unknown","attempt_number":1,"status":"accepted"}]
                ),
            )

        with self.assertRaisesRegex(ValueError, "attempt_number非法"):
            load_capture_progress(
                self.plan,
                self.write_attempts(
                    [{"sample_id":"a","attempt_number":0,"status":"accepted"}]
                ),
            )


if __name__ == "__main__":
    unittest.main()
