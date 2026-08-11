import json
import tempfile
import unittest
from pathlib import Path

from src.llm.processor import (
    ProcessOutcome,
)
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.storage.event_store import (
    ExperimentEventStore,
)


def make_event(
    *,
    event_type=(
        ExperimentEventType.OPERATION
    ),
    raw_text="加入缓冲液。",
    normalized_text="加入缓冲液。",
    session_id="session_001",
    segment_id=1,
) -> ExperimentEvent:
    return ExperimentEvent(
        event_type=event_type,
        raw_text=raw_text,
        normalized_text=normalized_text,
        entities=ExperimentEntities(
            action="加入",
            object="缓冲液",
        ),
        source_session_id=session_id,
        source_segment_id=segment_id,
    )


def make_outcome(
    events,
    *,
    degraded=False,
    error=None,
):
    return ProcessOutcome(
        value=LLMAnalysisResult(
            events=list(events)
        ),
        degraded=degraded,
        error=error,
    )


class ExperimentEventStoreTests(
    unittest.TestCase
):
    def test_saves_one_event(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "events.jsonl"
            )

            store = ExperimentEventStore(
                output_path=output_path
            )

            count = store.append_analysis(
                make_outcome(
                    [make_event()]
                )
            )

            self.assertEqual(
                count,
                1,
            )
            self.assertTrue(
                output_path.exists()
            )

            lines = (
                output_path
                .read_text(
                    encoding="utf-8"
                )
                .splitlines()
            )

            self.assertEqual(
                len(lines),
                1,
            )

            record = json.loads(
                lines[0]
            )

            self.assertEqual(
                record["event_type"],
                "operation",
            )
            self.assertEqual(
                record["raw_text"],
                "加入缓冲液。",
            )
            self.assertEqual(
                record[
                    "source_session_id"
                ],
                "session_001",
            )
            self.assertEqual(
                record[
                    "source_segment_id"
                ],
                1,
            )
            self.assertEqual(
                record["event_index"],
                1,
            )
            self.assertFalse(
                record["llm_degraded"]
            )
            self.assertIsNone(
                record["llm_error"]
            )
            self.assertIn(
                "saved_at",
                record,
            )

    def test_saves_multiple_events(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "events.jsonl"
            )

            store = ExperimentEventStore(
                output_path=output_path
            )

            operation = make_event(
                event_type=(
                    ExperimentEventType.OPERATION
                ),
                raw_text=(
                    "加入缓冲液，"
                    "溶液变蓝。"
                ),
                normalized_text=(
                    "加入缓冲液。"
                ),
            )

            observation = make_event(
                event_type=(
                    ExperimentEventType.OBSERVATION
                ),
                raw_text=(
                    "加入缓冲液，"
                    "溶液变蓝。"
                ),
                normalized_text=(
                    "溶液变为蓝色。"
                ),
            )

            count = store.append_analysis(
                make_outcome(
                    [
                        operation,
                        observation,
                    ]
                )
            )

            self.assertEqual(
                count,
                2,
            )

            records = [
                json.loads(line)
                for line in (
                    output_path
                    .read_text(
                        encoding="utf-8"
                    )
                    .splitlines()
                )
            ]

            self.assertEqual(
                [
                    record[
                        "event_index"
                    ]
                    for record in records
                ],
                [1, 2],
            )

            self.assertEqual(
                [
                    record[
                        "event_type"
                    ]
                    for record in records
                ],
                [
                    "operation",
                    "observation",
                ],
            )

    def test_saves_degraded_metadata(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "events.jsonl"
            )

            store = ExperimentEventStore(
                output_path=output_path
            )

            note = make_event(
                event_type=(
                    ExperimentEventType.NOTE
                ),
                raw_text=(
                    "使用营业枪加入缓冲液。"
                ),
                normalized_text=(
                    "使用营业枪加入缓冲液。"
                ),
            )

            store.append_analysis(
                make_outcome(
                    [note],
                    degraded=True,
                    error=(
                        "TimeoutError: timeout"
                    ),
                )
            )

            record = json.loads(
                output_path
                .read_text(
                    encoding="utf-8"
                )
                .splitlines()[0]
            )

            self.assertTrue(
                record["llm_degraded"]
            )
            self.assertEqual(
                record["llm_error"],
                "TimeoutError: timeout",
            )

    def test_chinese_is_not_ascii_escaped(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "events.jsonl"
            )

            store = ExperimentEventStore(
                output_path=output_path
            )

            store.append_analysis(
                make_outcome(
                    [make_event()]
                )
            )

            raw_content = (
                output_path
                .read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "加入缓冲液",
                raw_content,
            )
            self.assertNotIn(
                "\\u52a0",
                raw_content,
            )

    def test_rejects_missing_source(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            output_path = (
                Path(directory)
                / "events.jsonl"
            )

            store = ExperimentEventStore(
                output_path=output_path
            )

            event = make_event(
                session_id=None,
            )

            with self.assertRaises(
                ValueError
            ):
                store.append_analysis(
                    make_outcome(
                        [event]
                    )
                )

            self.assertFalse(
                output_path.exists()
            )


if __name__ == "__main__":
    unittest.main()