import json
import tempfile
import unittest
from pathlib import Path

from src.core.confirmation_record import (
    ConfirmationDecision,
    ConfirmationRecord,
)
from src.storage.confirmation_store import ConfirmationStore


def make_record(**changes) -> ConfirmationRecord:
    values = {
        "record_id": "session_001:answer:8",
        "session_id": "session_001",
        "clarification_id": "segment-7",
        "source_segment_id": 7,
        "answer_segment_id": 8,
        "answer_raw_text": "是的，是移液枪和500微升。",
        "answer_audio_path": "audio/answer_8.wav",
        "decision": ConfirmationDecision.CONFIRMED,
        "fully_resolved": True,
    }
    values.update(changes)
    return ConfirmationRecord(**values)


class ConfirmationRecordTests(unittest.TestCase):
    def test_to_dict_keeps_raw_text_and_serializes_enum(self):
        data = make_record().to_dict()

        self.assertEqual(data["decision"], "confirmed")
        self.assertEqual(
            data["answer_raw_text"],
            "是的，是移液枪和500微升。",
        )

    def test_fully_resolved_cannot_have_remaining_fields(self):
        with self.assertRaises(ValueError):
            make_record(
                fully_resolved=True,
                remaining_fields=("duration",),
            )

    def test_answer_must_follow_source_segment(self):
        with self.assertRaises(ValueError):
            make_record(answer_segment_id=7)

    def test_corrected_decision_requires_corrected_fields(self):
        with self.assertRaises(ValueError):
            make_record(
                decision=ConfirmationDecision.CORRECTED,
                fully_resolved=False,
            )


class ConfirmationStoreTests(unittest.TestCase):
    def test_appends_utf8_jsonl_record(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "confirmations.jsonl"
            store = ConfirmationStore(output_path=output_path)

            store.append(make_record())

            lines = output_path.read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(lines), 1)

            stored = json.loads(lines[0])
            self.assertEqual(stored["record_id"], "session_001:answer:8")
            self.assertEqual(stored["decision"], "confirmed")
            self.assertEqual(
                stored["answer_raw_text"],
                "是的，是移液枪和500微升。",
            )
            self.assertIn("saved_at", stored)

    def test_saves_unresolved_remaining_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "confirmations.jsonl"
            store = ConfirmationStore(output_path=output_path)
            store.append(
                make_record(
                    fully_resolved=False,
                    remaining_fields=("duration",),
                )
            )

            stored = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                ).splitlines()[0]
            )

            self.assertFalse(stored["fully_resolved"])
            self.assertEqual(stored["remaining_fields"], ["duration"])

    def test_rejects_duplicate_record_id_without_second_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "confirmations.jsonl"
            store = ConfirmationStore(output_path=output_path)
            record = make_record()
            store.append(record)

            with self.assertRaises(ValueError):
                store.append(record)

            self.assertEqual(
                len(
                    output_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                ),
                1,
            )

    def test_invalid_existing_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "confirmations.jsonl"
            original = "这不是JSON\n"
            output_path.write_text(original, encoding="utf-8")
            store = ConfirmationStore(output_path=output_path)

            with self.assertRaises(ValueError):
                store.append(make_record())

            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                original,
            )


if __name__ == "__main__":
    unittest.main()
