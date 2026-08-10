import json
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from src.asr.schemas import (
    ASR_EVIDENCE_SCHEMA_VERSION,
    ASRResult,
    TranscriptCorrectionCandidate,
)
from src.storage.result_store import ASRResultStore


def make_result() -> ASRResult:
    return ASRResult(
        asr_transcript="用一夜枪加入500微升缓冲液。",
        asr_model_raw_text=(
            "<|zh|><|NEUTRAL|><|Speech|>"
            "用一夜枪加入500微升缓冲液。"
        ),
        audio_path="C:/evidence/sample.wav",
        audio_duration_seconds=2.5,
        recognition_seconds=0.2,
        model="test-asr",
        language="zh",
    )


def legacy_payload() -> dict:
    return {
        "text": "用一夜枪加入500微升缓冲液。",
        "raw_text": (
            "<|zh|><|NEUTRAL|><|Speech|>"
            "用一夜枪加入500微升缓冲液。"
        ),
        "audio_path": "C:/evidence/sample.wav",
        "audio_duration_seconds": 2.5,
        "recognition_seconds": 0.2,
        "model": "test-asr",
        "language": "zh",
        "is_final": True,
    }


class ASREvidenceContractTests(unittest.TestCase):
    def test_v2_serialization_uses_unambiguous_names(self):
        payload = make_result().to_dict()

        self.assertEqual(
            payload["schema_version"],
            ASR_EVIDENCE_SCHEMA_VERSION,
        )
        self.assertEqual(
            payload["asr_transcript"],
            "用一夜枪加入500微升缓冲液。",
        )
        self.assertIn("asr_model_raw_text", payload)
        self.assertNotIn("text", payload)
        self.assertNotIn("raw_text", payload)

    def test_legacy_v1_payload_remains_readable(self):
        payload = legacy_payload()

        result = ASRResult.from_dict(payload)

        self.assertEqual(result.asr_transcript, payload["text"])
        self.assertEqual(
            result.asr_model_raw_text,
            payload["raw_text"],
        )
        self.assertEqual(payload, legacy_payload())

    def test_legacy_properties_are_read_only_transition_aliases(self):
        result = make_result()

        self.assertEqual(result.text, result.asr_transcript)
        self.assertEqual(
            result.raw_text,
            result.asr_model_raw_text,
        )
        with self.assertRaises(FrozenInstanceError):
            result.text = "覆盖"

    def test_rejects_mixed_old_and_new_fields(self):
        payload = make_result().to_dict()
        payload["text"] = "伪装的旧字段"

        with self.assertRaisesRegex(
            ValueError,
            "未知字段",
        ):
            ASRResult.from_dict(payload)

    def test_rejects_unknown_schema_or_invalid_metrics(self):
        payload = make_result().to_dict()
        payload["schema_version"] = 99

        with self.assertRaisesRegex(
            ValueError,
            "不支持的ASR证据",
        ):
            ASRResult.from_dict(payload)
        with self.assertRaisesRegex(ValueError, "有限值"):
            ASRResult(
                asr_transcript="文本",
                asr_model_raw_text="原始文本",
                recognition_seconds=float("nan"),
            )

    def test_correction_is_separate_and_cannot_mutate_evidence(self):
        evidence = make_result()
        correction = TranscriptCorrectionCandidate(
            source_asr_transcript=evidence.asr_transcript,
            candidate_transcript=(
                "用移液枪加入500微升缓冲液。"
            ),
            reason="专业词近音候选",
        )

        self.assertEqual(
            evidence.asr_transcript,
            "用一夜枪加入500微升缓冲液。",
        )
        self.assertTrue(correction.requires_confirmation)
        with self.assertRaises(FrozenInstanceError):
            correction.candidate_transcript = "覆盖证据"

    def test_correction_must_differ_from_source(self):
        with self.assertRaisesRegex(ValueError, "必须与源转写不同"):
            TranscriptCorrectionCandidate(
                source_asr_transcript="水浴60度",
                candidate_transcript="水浴60度",
                reason="无实际修改",
            )


class ASREvidenceStoreTests(unittest.TestCase):
    def test_new_append_writes_v2_and_loads_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "asr.jsonl"
            store = ASRResultStore(output_path)
            store.append(make_result(), "session-1", 1)
            original_text = output_path.read_text(encoding="utf-8")

            records = store.load_all()

            self.assertEqual(len(records), 1)
            self.assertEqual(
                records[0].result.asr_transcript,
                make_result().asr_transcript,
            )
            self.assertEqual(records[0].session_id, "session-1")
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                original_text,
            )
            stored = json.loads(original_text)
            self.assertEqual(stored["schema_version"], 2)

    def test_historical_v1_jsonl_loads_without_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "asr.jsonl"
            old_record = legacy_payload()
            old_record.update({
                "session_id": "legacy-session",
                "segment_id": 3,
                "saved_at": "2026-08-04T20:53:11+08:00",
            })
            original_text = (
                json.dumps(old_record, ensure_ascii=False) + "\n"
            )
            output_path.write_text(
                original_text,
                encoding="utf-8",
            )

            records = ASRResultStore(output_path).load_all()

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].segment_id, 3)
            self.assertEqual(
                records[0].result.asr_model_raw_text,
                old_record["raw_text"],
            )
            self.assertEqual(
                output_path.read_text(encoding="utf-8"),
                original_text,
            )

    def test_damaged_record_reports_line_without_partial_result(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "asr.jsonl"
            output_path.write_text(
                json.dumps({"text": "缺少来源"}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "第1行"):
                ASRResultStore(output_path).load_all()


if __name__ == "__main__":
    unittest.main()
