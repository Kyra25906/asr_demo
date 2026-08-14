import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_session_context import (
    load_records,
    session_summary,
)


def _write_jsonl(path: Path, records) -> None:
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def _asr_record(session_id, segment_id, transcript):
    return {
        "schema_version": 2,
        "asr_transcript": transcript,
        "session_id": session_id,
        "segment_id": segment_id,
        "is_final": True,
    }


def _event_record(session_id, segment_id, event_type="operation"):
    return {
        "event_type": event_type,
        "raw_text": "原文",
        "normalized_text": "规范",
        "source_session_id": session_id,
        "source_segment_id": segment_id,
        "event_index": 1,
    }


class LoadRecordsTests(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            records = load_records(Path(temp_dir) / "missing.jsonl")
        self.assertEqual(records, [])

    def test_corrupt_line_is_skipped_but_others_load(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "store.jsonl"
            path.write_text(
                "{not-json}\n"
                + json.dumps(_asr_record("s1", 1, "文本")) + "\n",
                encoding="utf-8",
            )
            records = load_records(path)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["session_id"], "s1")


class SessionSummaryTests(unittest.TestCase):
    def test_summarizes_only_target_session(self):
        asr = [
            _asr_record("target", 1, "第一段"),
            _asr_record("target", 2, "第二段"),
            _asr_record("other", 1, "别人的"),
        ]
        events = [
            _event_record("target", 1),
            _event_record("target", 2),
            _event_record("other", 1),
        ]
        summary = session_summary("target", asr, events)

        self.assertEqual(summary["asr_segments"], 2)
        self.assertEqual(summary["event_count"], 2)
        self.assertEqual(summary["expected_context_count"], 2)
        self.assertEqual(
            summary["segments_with_events"],
            {1: 1, 2: 1},
        )
        self.assertEqual(
            summary["asr_transcripts"],
            ["第一段", "第二段"],
        )

    def test_aggregation_ignores_input_order(self):
        events = [
            _event_record("s", 2),
            _event_record("s", 1),
        ]
        summary = session_summary("s", [], events)

        self.assertEqual(
            summary["segments_with_events"],
            {1: 1, 2: 1},
        )
        self.assertEqual(summary["event_count"], 2)

    def test_unknown_session_is_empty(self):
        summary = session_summary(
            "ghost",
            [_asr_record("real", 1, "文本")],
            [_event_record("real", 1)],
        )

        self.assertEqual(summary["asr_segments"], 0)
        self.assertEqual(summary["event_count"], 0)
        self.assertEqual(summary["expected_context_count"], 0)


if __name__ == "__main__":
    unittest.main()
