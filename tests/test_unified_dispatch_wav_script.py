import tempfile
import unittest
import wave
from pathlib import Path

from scripts.evaluate_unified_dispatch_wav import (
    SAFE_REPORT_FIELDS,
    build_safe_observation,
)
from src.asr.schemas import ASRResult
from src.llm.client import LLMClientError, LLMGenerationResult
from src.llm.unified_processor import UnifiedUnderstandingProcessor


class FakeASRBackend:
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    def recognize(self, audio_path, *, language="auto") -> ASRResult:
        return ASRResult(
            asr_transcript=self.transcript,
            asr_model_raw_text=f"<|zh|>{self.transcript}<|Speech|>",
            audio_path=str(audio_path),
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fake-asr",
            language=language,
        )


class FixedExperimentClient:
    def generate_json(self, *, system_prompt, user_prompt):
        return LLMGenerationResult(
            content=(
                '{"input_kind":"experiment","experiment":{"analysis":'
                '{"events":[{"event_type":"operation",'
                '"raw_text":"加入五毫升缓冲液。",'
                '"normalized_text":"加入5毫升缓冲液。",'
                '"entities":{"action":"加入","object":"缓冲液",'
                '"instrument":null,"amount_value":"5",'
                '"amount_unit":"毫升","concentration":null,'
                '"temperature":null,"duration":null,"condition":null,'
                '"observation":null},"missing_fields":[],'
                '"needs_confirmation":false,"confirmation_reason":null}],'
                '"should_ask_follow_up":false,"follow_up_question":null,'
                '"assistant_reply":null}},"control":null,"uncertain":null}'
            ),
            attempts=1,
            processing_seconds=0.2,
        )


class FailingClient:
    def generate_json(self, *, system_prompt, user_prompt):
        raise LLMClientError(
            "secret upstream detail",
            attempts=2,
            processing_seconds=0.3,
        )


class UnifiedDispatchWavScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.audio_path = Path(self.temporary_directory.name) / "fixed.wav"
        with wave.open(str(self.audio_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b"\x00\x00" * 160)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_report_uses_strict_redacted_field_whitelist(self):
        report = build_safe_observation(
            asr_backend=FakeASRBackend("加入五毫升缓冲液。"),
            processor=UnifiedUnderstandingProcessor(FixedExperimentClient()),
            audio_path=self.audio_path,
        )
        self.assertEqual(set(report), SAFE_REPORT_FIELDS)
        serialized = str(report)
        self.assertNotIn("<|zh|>", serialized)
        self.assertNotIn(self.temporary_directory.name, serialized)
        self.assertNotIn("raw_response", serialized)
        self.assertEqual(report["destination"], "experiment_pipeline")

    def test_real_processor_failure_stops_at_degraded_note(self):
        report = build_safe_observation(
            asr_backend=FakeASRBackend("加入五毫升缓冲液。"),
            processor=UnifiedUnderstandingProcessor(FailingClient()),
            audio_path=self.audio_path,
        )
        self.assertTrue(report["degraded"])
        self.assertEqual(report["destination"], "degraded_note")
        self.assertEqual(report["permission"], "forward_degraded_note")
        self.assertEqual(report["llm_attempts"], 2)
        self.assertNotIn("secret upstream detail", str(report))


if __name__ == "__main__":
    unittest.main()
