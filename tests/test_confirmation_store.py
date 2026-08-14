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


class FromExecutedConfirmationTests(unittest.TestCase):
    def test_builds_confirmed_record_with_execution_fields(self):
        record = ConfirmationRecord.from_executed_confirmation(
            session_id="session_002",
            clarification_id="segment-9",
            source_segment_id=9,
            answer_segment_id=10,
            answer_raw_text="是的，是水浴。",
            answer_audio_path="audio/answer_10.wav",
            fully_resolved=True,
            remaining_fields=(),
        )

        self.assertEqual(record.decision, ConfirmationDecision.CONFIRMED)
        self.assertEqual(record.clarification_id, "segment-9")
        self.assertEqual(record.source_segment_id, 9)
        self.assertEqual(record.answer_segment_id, 10)
        self.assertEqual(
            record.record_id,
            "session_002:confirmation:10:segment-9",
        )

    def test_partial_confirmation_keeps_remaining_fields(self):
        record = ConfirmationRecord.from_executed_confirmation(
            session_id="session_002",
            clarification_id="segment-11",
            source_segment_id=11,
            answer_segment_id=12,
            answer_raw_text="是的。",
            answer_audio_path="audio/answer_12.wav",
            fully_resolved=False,
            remaining_fields=("duration",),
        )

        self.assertFalse(record.fully_resolved)
        self.assertEqual(record.remaining_fields, ("duration",))

    def test_rejects_answer_in_source_segment_or_earlier(self):
        with self.assertRaisesRegex(ValueError, "answer_segment_id"):
            ConfirmationRecord.from_executed_confirmation(
                session_id="s",
                clarification_id="segment-1",
                source_segment_id=1,
                answer_segment_id=1,
                answer_raw_text="是的。",
                answer_audio_path="audio/a.wav",
                fully_resolved=True,
                remaining_fields=(),
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
