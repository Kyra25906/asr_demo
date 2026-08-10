import json
import unittest

from src.core.unified_understanding import (
    UnifiedInputKind,
    UnifiedUnderstandingError,
    build_degraded_understanding,
    parse_unified_understanding,
)
from src.core.interaction_command import InteractionCommandType
from src.llm.schemas import ExperimentEventType


RAW_TEXT = "加入五毫升缓冲液并搅拌。"


def analysis_payload(raw_text=RAW_TEXT):
    return {
        "events": [{
            "event_type": "operation",
            "raw_text": raw_text,
            "normalized_text": "加入5毫升缓冲液并搅拌。",
            "entities": {
                "action": "加入并搅拌", "object": "缓冲液",
                "instrument": None, "amount_value": "5",
                "amount_unit": "毫升", "concentration": None,
                "temperature": None, "duration": None,
                "condition": None, "observation": None,
            },
            "missing_fields": [],
            "needs_confirmation": False,
            "confirmation_reason": None,
        }],
        "should_ask_follow_up": False,
        "follow_up_question": None,
        "assistant_reply": "已记录。",
    }


def parse(data):
    return parse_unified_understanding(
        json.dumps(data, ensure_ascii=False),
        expected_raw_text=RAW_TEXT,
        session_id="session-1",
        segment_id=7,
    )


class UnifiedUnderstandingContractTests(unittest.TestCase):
    def test_parses_experiment_and_injects_trusted_source_fields(self):
        result = parse({
            "input_kind": "experiment",
            "experiment": {"analysis": analysis_payload()},
            "control": None,
            "uncertain": None,
        })

        self.assertEqual(result.input_kind, UnifiedInputKind.EXPERIMENT)
        self.assertEqual(result.raw_text, RAW_TEXT)
        event = result.experiment.analysis.events[0]
        self.assertEqual(event.raw_text, RAW_TEXT)
        self.assertEqual(event.source_session_id, "session-1")
        self.assertEqual(event.source_segment_id, 7)

    def test_parses_matched_control_without_authorizing_execution(self):
        result = parse({
            "input_kind": "control",
            "experiment": None,
            "control": {"intent": {
                "status": "matched",
                "command_type": "end_session",
                "target_question_number": None,
                "answer_text": None,
                "reason": "用户可能希望结束会话。",
            }},
            "uncertain": None,
        })

        self.assertEqual(result.input_kind, UnifiedInputKind.CONTROL)
        self.assertEqual(
            result.control.intent.command_type,
            InteractionCommandType.END_SESSION,
        )
        self.assertEqual(result.raw_text, RAW_TEXT)

    def test_uncertain_contains_only_abstention_reason(self):
        result = parse({
            "input_kind": "uncertain",
            "experiment": None,
            "control": None,
            "uncertain": {"reason": "无法可靠判断输入类型。"},
        })

        self.assertEqual(result.input_kind, UnifiedInputKind.UNCERTAIN)
        self.assertEqual(result.uncertain.reason, "无法可靠判断输入类型。")
        self.assertIsNone(result.control)
        self.assertIsNone(result.experiment)

    def test_rejects_missing_extra_and_mixed_branches(self):
        valid = {
            "input_kind": "uncertain",
            "experiment": None,
            "control": None,
            "uncertain": {"reason": "不确定。"},
        }
        invalid = (
            {key: value for key, value in valid.items() if key != "control"},
            {**valid, "execute_now": True},
            {**valid, "control": {"intent": {}}},
        )
        for data in invalid:
            with self.subTest(data=data):
                with self.assertRaises(UnifiedUnderstandingError):
                    parse(data)

    def test_rejects_raw_text_overwrite_and_branch_extra_fields(self):
        wrong_raw = {
            "input_kind": "experiment",
            "experiment": {"analysis": analysis_payload("伪造原文")},
            "control": None,
            "uncertain": None,
        }
        smuggled = {
            "input_kind": "uncertain",
            "experiment": None,
            "control": None,
            "uncertain": {"reason": "不确定。", "answer_text": "是"},
        }
        for data in (wrong_raw, smuggled):
            with self.subTest(data=data):
                with self.assertRaises(UnifiedUnderstandingError):
                    parse(data)

    def test_rejects_uncertain_candidate_disguised_as_control(self):
        with self.assertRaisesRegex(UnifiedUnderstandingError, "matched"):
            parse({
                "input_kind": "control",
                "experiment": None,
                "control": {"intent": {
                    "status": "uncertain",
                    "command_type": None,
                    "target_question_number": None,
                    "answer_text": None,
                    "reason": "不确定。",
                }},
                "uncertain": None,
            })

    def test_rejects_missing_fields_without_follow_up(self):
        analysis = analysis_payload()
        analysis["events"][0]["missing_fields"] = [
            "temperature", "duration",
        ]
        with self.assertRaisesRegex(
            UnifiedUnderstandingError,
            "追问标志",
        ):
            parse({
                "input_kind": "experiment",
                "experiment": {"analysis": analysis},
                "control": None,
                "uncertain": None,
            })

    def test_rejects_confirmation_need_without_follow_up(self):
        analysis = analysis_payload()
        event = analysis["events"][0]
        event["needs_confirmation"] = True
        event["confirmation_reason"] = "名称可能识别错误。"
        with self.assertRaisesRegex(
            UnifiedUnderstandingError,
            "追问标志",
        ):
            parse({
                "input_kind": "experiment",
                "experiment": {"analysis": analysis},
                "control": None,
                "uncertain": None,
            })

    def test_rejects_follow_up_without_event_reason(self):
        analysis = analysis_payload()
        analysis["should_ask_follow_up"] = True
        analysis["follow_up_question"] = "请补充信息。"
        with self.assertRaisesRegex(
            UnifiedUnderstandingError,
            "追问标志",
        ):
            parse({
                "input_kind": "experiment",
                "experiment": {"analysis": analysis},
                "control": None,
                "uncertain": None,
            })

    def test_format_failure_can_degrade_to_unclassified_note(self):
        result = build_degraded_understanding(
            raw_text=RAW_TEXT,
            session_id="session-1",
            segment_id=7,
            reason="非法JSON",
        )

        self.assertIsNone(result.control)
        event = result.experiment.analysis.events[0]
        self.assertEqual(event.event_type, ExperimentEventType.NOTE)
        self.assertEqual(event.raw_text, RAW_TEXT)
        self.assertTrue(event.needs_confirmation)
        self.assertTrue(result.experiment.analysis.should_ask_follow_up)
        self.assertTrue(result.experiment.analysis.follow_up_question)


if __name__ == "__main__":
    unittest.main()
