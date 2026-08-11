import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_pre_roll_real import (
    PROMPTS,
    load_next_attempt_numbers,
)


class PreRollRealValidationTests(unittest.TestCase):
    def test_defines_three_repetitions_for_each_sentence(self):
        self.assertEqual(len(PROMPTS), 9)
        self.assertEqual(
            [prompt.prompt_text for prompt in PROMPTS].count("这个先跳过。"),
            3,
        )
        self.assertEqual(
            [prompt.prompt_text for prompt in PROMPTS].count(
                "查看待确认问题。"
            ),
            3,
        )
        self.assertEqual(
            [prompt.prompt_text for prompt in PROMPTS].count("跳过这个问题。"),
            3,
        )

    def test_critical_terms_cover_sentence_initials(self):
        self.assertEqual(PROMPTS[0].critical_terms[0], "这")
        self.assertEqual(PROMPTS[3].critical_terms[0], "查")
        self.assertEqual(PROMPTS[6].critical_terms[0], "跳")

    def test_existing_attempts_advance_number_per_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.jsonl"
            records = [
                {"sample_id": "sample-a", "attempt_number": 1},
                {"sample_id": "sample-a", "attempt_number": 3},
                {"sample_id": "sample-b", "attempt_number": 2},
            ]
            path.write_text(
                "\n".join(json.dumps(record) for record in records),
                encoding="utf-8",
            )

            numbers = load_next_attempt_numbers(path)

        self.assertEqual(numbers, {"sample-a": 4, "sample-b": 3})

    def test_damaged_existing_record_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "attempts.jsonl"
            path.write_text("not-json\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "第 1 行损坏"):
                load_next_attempt_numbers(path)


if __name__ == "__main__":
    unittest.main()
