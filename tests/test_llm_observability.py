import json
import tempfile
import unittest
from pathlib import Path

from src.llm.client import LLMClientError, LLMGenerationResult
from src.llm.processor import ExperimentLLMProcessor, ProcessOutcome
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)
from src.storage.event_store import ExperimentEventStore


def make_valid_response(raw_text: str) -> str:
    return json.dumps(
        {
            "events": [
                {
                    "event_type": "operation",
                    "raw_text": raw_text,
                    "normalized_text": raw_text,
                    "entities": {
                        "action": "加入",
                        "object": "缓冲液",
                        "instrument": None,
                        "amount_value": None,
                        "amount_unit": None,
                        "concentration": None,
                        "temperature": None,
                        "duration": None,
                        "condition": None,
                        "observation": None,
                    },
                    "missing_fields": [],
                    "needs_confirmation": False,
                    "confirmation_reason": None,
                }
            ],
            "should_ask_follow_up": False,
            "follow_up_question": None,
            "assistant_reply": "已记录。",
        },
        ensure_ascii=False,
    )


class SuccessfulClient:
    def generate_json(self, *, system_prompt, user_prompt):
        return LLMGenerationResult(
            content=make_valid_response("加入缓冲液。"),
            attempts=2,
            processing_seconds=1.234,
        )


class FailedClient:
    def generate_json(self, *, system_prompt, user_prompt):
        raise LLMClientError(
            "两次空响应",
            attempts=2,
            processing_seconds=2.345,
        )


class LLMObservabilityTests(unittest.TestCase):
    def test_processor_keeps_success_metrics(self):
        outcome = ExperimentLLMProcessor(
            SuccessfulClient()
        ).analyze_segment(
            raw_text="加入缓冲液。",
            session_id="session_001",
            segment_id=1,
        )

        self.assertFalse(outcome.degraded)
        self.assertEqual(outcome.llm_attempts, 2)
        self.assertEqual(
            outcome.llm_processing_seconds,
            1.234,
        )

    def test_processor_keeps_failure_metrics(self):
        outcome = ExperimentLLMProcessor(
            FailedClient()
        ).analyze_segment(
            raw_text="加入缓冲液。",
            session_id="session_001",
            segment_id=1,
        )

        self.assertTrue(outcome.degraded)
        self.assertEqual(outcome.llm_attempts, 2)
        self.assertEqual(
            outcome.llm_processing_seconds,
            2.345,
        )

    def test_event_store_writes_metrics(self):
        event = ExperimentEvent(
            event_type=ExperimentEventType.OPERATION,
            raw_text="加入缓冲液。",
            normalized_text="加入缓冲液。",
            entities=ExperimentEntities(
                action="加入",
                object="缓冲液",
            ),
            source_session_id="session_001",
            source_segment_id=1,
        )
        outcome = ProcessOutcome(
            value=LLMAnalysisResult(events=[event]),
            degraded=False,
            llm_attempts=2,
            llm_processing_seconds=1.234,
        )

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "events.jsonl"
            ExperimentEventStore(output_path).append_analysis(outcome)
            record = json.loads(
                output_path.read_text(
                    encoding="utf-8"
                ).splitlines()[0]
            )

        self.assertEqual(record["llm_attempts"], 2)
        self.assertEqual(
            record["llm_processing_seconds"],
            1.234,
        )


if __name__ == "__main__":
    unittest.main()
